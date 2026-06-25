from flask import Flask, request, render_template_string
from rembg import remove

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Image Editor</title>

<style>
body { font-family: sans-serif; margin:0; padding:10px; background:#f5f5f5; }
.container { max-width:500px; margin:auto; }
canvas { width:100%; background:white; border-radius:12px; touch-action:none; }
.queue { display:flex; overflow:auto; gap:8px; margin-top:10px; }
.queue img { width:60px; height:60px; border-radius:8px; }
.active { border:2px solid black; }
button { padding:10px; border:none; border-radius:10px; background:black; color:white; margin-top:8px; width:100%; }
</style>
</head>

<body>
<div class="container">

<h2>AI Editor</h2>
<input type="file" id="fileInput" multiple>

<div class="queue" id="queue"></div>
<canvas id="canvas"></canvas>

<button onclick="smartCenter()">Smart Center</button>
<button onclick="cropMode()">Crop</button>
<button onclick="applyCrop()">Apply Crop</button>
<button onclick="download()">Download</button>

</div>

<script>
let canvas = document.getElementById("canvas");
let ctx = canvas.getContext("2d");

let images = [];
let current = 0;

let SNAP_THRESHOLD = 10;
let showVGuide = false;
let showHGuide = false;

// IMAGE STATE
function createState(src){
    let img = new Image();
    img.src = src;

    return { img, x:0, y:0, scale:1 };
}

// FILE UPLOAD
document.getElementById("fileInput").onchange = async (e)=>{
    for(let file of e.target.files){
        let form = new FormData();
        form.append("image", file);

        let res = await fetch("/remove-bg",{method:"POST",body:form});
        let blob = await res.blob();
        let url = URL.createObjectURL(blob);

        let state = createState(url);
        images.push(state);

        state.img.onload = ()=>{
            canvas.width = state.img.width;
            canvas.height = state.img.height;
            draw();
        };
    }
    renderQueue();
};

// QUEUE UI
function renderQueue(){
    let q = document.getElementById("queue");
    q.innerHTML="";
    images.forEach((img,i)=>{
        let el=document.createElement("img");
        el.src=img.img.src;
        if(i===current) el.classList.add("active");
        el.onclick=()=>{ current=i; renderQueue(); draw(); }
        q.appendChild(el);
    });
}

function cur(){ return images[current]; }

// DRAW FUNCTION
function draw(){
    let c=cur();
    if(!c) return;

    ctx.clearRect(0,0,canvas.width,canvas.height);

    let w = c.img.width * c.scale;
    let h = c.img.height * c.scale;

    ctx.drawImage(c.img, c.x, c.y, w, h);

    // Guides
    if(showVGuide){
        ctx.strokeStyle="blue";
        ctx.beginPath();
        ctx.moveTo(canvas.width/2,0);
        ctx.lineTo(canvas.width/2,canvas.height);
        ctx.stroke();
    }

    if(showHGuide){
        ctx.strokeStyle="blue";
        ctx.beginPath();
        ctx.moveTo(0,canvas.height/2);
        ctx.lineTo(canvas.width,canvas.height/2);
        ctx.stroke();
    }

    // Crop box
    if(cropping){
        ctx.strokeStyle="red";
        ctx.strokeRect(crop.x,crop.y,crop.w,crop.h);
    }
}

// SNAP LOGIC
function applySnapping(c){
    showVGuide = false;
    showHGuide = false;

    let w = c.img.width * c.scale;
    let h = c.img.height * c.scale;

    let cx = c.x + w/2;
    let cy = c.y + h/2;

    let canvasCX = canvas.width/2;
    let canvasCY = canvas.height/2;

    if(Math.abs(cx - canvasCX) < SNAP_THRESHOLD){
        c.x = canvasCX - w/2;
        showVGuide = true;
    }

    if(Math.abs(cy - canvasCY) < SNAP_THRESHOLD){
        c.y = canvasCY - h/2;
        showHGuide = true;
    }
}

// TOUCH CONTROLS
let dragging=false;
let lastX,lastY;
let lastDist=null;

canvas.addEventListener("touchstart",e=>{
    if(e.touches.length===1){
        dragging=true;
        lastX=e.touches[0].clientX;
        lastY=e.touches[0].clientY;
    }else if(e.touches.length===2){
        lastDist=getDist(e);
    }
});

canvas.addEventListener("touchmove",e=>{
    let c=cur();

    if(e.touches.length===1 && dragging){
        let t=e.touches[0];
        let dx=t.clientX-lastX;
        let dy=t.clientY-lastY;

        c.x+=dx;
        c.y+=dy;

        applySnapping(c);

        lastX=t.clientX;
        lastY=t.clientY;
    }

    if(e.touches.length===2){
        let d=getDist(e);
        let scaleFactor=d/lastDist;
        c.scale*=scaleFactor;

        applySnapping(c);

        lastDist=d;
    }

    draw();
});

canvas.addEventListener("touchend",()=>dragging=false);

function getDist(e){
    let dx=e.touches[0].clientX - e.touches[1].clientX;
    let dy=e.touches[0].clientY - e.touches[1].clientY;
    return Math.sqrt(dx*dx+dy*dy);
}

// SMART CENTER
function smartCenter(){
    let c=cur();

    let temp=document.createElement("canvas");
    temp.width=c.img.width;
    temp.height=c.img.height;

    let tctx=temp.getContext("2d");
    tctx.drawImage(c.img,0,0);

    let data=tctx.getImageData(0,0,temp.width,temp.height).data;

    let minX=9999,minY=9999,maxX=0,maxY=0;

    for(let y=0;y<temp.height;y++){
        for(let x=0;x<temp.width;x++){
            let i=(y*temp.width+x)*4;
            if(data[i+3]>10){
                if(x<minX)minX=x;
                if(y<minY)minY=y;
                if(x>maxX)maxX=x;
                if(y>maxY)maxY=y;
            }
        }
    }

    let w=maxX-minX;
    let h=maxY-minY;

    c.x=(canvas.width-w)/2 - minX;
    c.y=(canvas.height-h)/2 - minY;

    draw();
}

// CROPPING
let cropping=false;
let crop={x:50,y:50,w:200,h:200};

function cropMode(){ cropping=true; }

canvas.addEventListener("mousedown",e=>{
    if(!cropping)return;
    crop.x=e.offsetX;
    crop.y=e.offsetY;
});

canvas.addEventListener("mousemove",e=>{
    if(!cropping)return;
    crop.w=e.offsetX-crop.x;
    crop.h=e.offsetY-crop.y;
    draw();
});

function applyCrop(){
    let data=ctx.getImageData(crop.x,crop.y,crop.w,crop.h);

    canvas.width=crop.w;
    canvas.height=crop.h;

    ctx.putImageData(data,0,0);
    cropping=false;
}

// DOWNLOAD
function download(){
    let a=document.createElement("a");
    a.download="image.png";
    a.href=canvas.toDataURL();
    a.click();
}
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    return remove(request.files["image"].read()), 200, {'Content-Type': 'image/png'}

if __name__ == "__main__":
    app.run(debug=True)
