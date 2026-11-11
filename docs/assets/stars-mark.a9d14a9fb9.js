/* Brand-coloured dots gather into the real logo as its section scrolls in.
   Geometry is measured only when layout changes. The animation catches up with
   scrolling, and while free dots are on screen it keeps drifting gently even
   with no scroll, so the swarm never looks frozen. It sleeps only when the
   canvas is off screen, before the dots appear, or once the logo is complete.
   Reduced motion keeps the real logo visible without creating a canvas. */
(function(){
  var mark=document.querySelector('.cta-mark'), img=mark&&mark.querySelector('img'), band=mark&&mark.closest('section');
  if(!mark||!img||!band||!window.requestAnimationFrame) return;
  var motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  var cv=null,g=null,ready=false,raf=0,layoutPending=true;
  var W=0,CH=0,dpr=1,P=[],vh=0,cvTop=0,markTop=0,L=0,T=0,MW=0,MH=0,end=0,span=1;
  var progress=-1,last=0,time=0,lastOpacity='',lastFilter='',canvasEmpty=true;
  var PAL=['#8DC63F','#ED1C24','#00AEEF','#F7941D','#58595B'];
  var RGB=[[141,198,63],[237,28,36],[0,174,239],[247,148,29],[88,89,91]];
  function clamp(x){return Math.min(Math.max(x,0),1);}
  function nearest(r,gr,b){
    var best=0,bd=1e9;
    for(var i=0;i<RGB.length;i++){
      var d=Math.pow(r-RGB[i][0],2)+Math.pow(gr-RGB[i][1],2)+Math.pow(b-RGB[i][2],2);
      if(d<bd){bd=d;best=i;}
    }
    return best;
  }
  function build(){
    var sw=210,sh=Math.round(sw*img.naturalHeight/img.naturalWidth),oc=document.createElement('canvas');
    oc.width=sw;oc.height=sh;
    var og=oc.getContext('2d'),data;
    if(!og) return false;
    try{og.drawImage(img,0,0,sw,sh);data=og.getImageData(0,0,sw,sh).data;}catch(e){return false;}
    var pts=[];
    for(var y=0;y<sh;y++) for(var x=0;x<sw;x++){
      var i=(y*sw+x)*4;
      if(data[i+3]<140||(data[i]>235&&data[i+1]>235&&data[i+2]>235)) continue;
      pts.push([(x+Math.random())/sw,(y+Math.random())/sh,nearest(data[i],data[i+1],data[i+2])]);
    }
    var limit=window.innerWidth<768?800:1600;
    if(pts.length>limit){
      for(var n=0;n<limit;n++){
        var j=n+Math.floor(Math.random()*(pts.length-n)),q=pts[n];pts[n]=pts[j];pts[j]=q;
      }
      pts.length=limit;
    }
    P=pts.map(function(t){return {tx:t[0],ty:t[1],c:t[2],s:Math.floor(Math.random()*4),hx:Math.random(),hy:Math.random(),z:0.2+0.8*Math.pow(Math.random(),1.6),d:Math.random(),ph:Math.random()*6.283,sw:(Math.random()-.5)*2};});
    return P.length>0;
  }
  function stop(){if(raf) cancelAnimationFrame(raf);raf=0;last=0;}
  function measure(){
    /* Batch all layout reads before canvas/style writes. Scroll frames use only
       these document coordinates and scrollY, never getBoundingClientRect. */
    var b=band.getBoundingClientRect(),r=mark.getBoundingClientRect(),scroll=window.scrollY;
    var height=window.innerHeight,w=document.documentElement.clientWidth,docHeight=document.documentElement.scrollHeight;
    var lead=Math.round(height*0.6),top=Math.round(b.top+scroll-lead),h=Math.max(1,Math.round(b.height+lead));
    var density=Math.min(window.devicePixelRatio||1,w<768?1.25:1.5,Math.sqrt(2500000/(Math.max(w,1)*h)));
    vh=height;cvTop=top;markTop=r.top+scroll;L=r.left;T=markTop-top;MW=r.width;MH=r.height;
    end=Math.max(vh*0.50,markTop-(docHeight-vh)+24);span=Math.max(vh*1.0-end,vh*0.3);   /* starts as the mark enters the screen, fully formed when its top reaches mid-screen */
    if(W!==w||CH!==h||dpr!==density){
      W=w;CH=h;dpr=density;cv.style.width=w+'px';cv.style.height=h+'px';
      cv.width=Math.max(1,Math.round(w*dpr));cv.height=Math.max(1,Math.round(h*dpr));
      g.setTransform(dpr,0,0,dpr,0,0);canvasEmpty=true;
    }
    if(cv.style.top!==top+'px') cv.style.top=top+'px';
    layoutPending=false;
  }
  function target(){return clamp((end+span-markTop+window.scrollY)/span);}
  function visible(){var top=cvTop-window.scrollY;return top<vh&&top+CH>0;}
  function wake(){
    if(!ready||motion.matches||document.hidden) return;
    if(!layoutPending&&!visible()){
      /* Keep reverse scrolling consistent without rendering offscreen. */
      progress=target();stop();return;
    }
    if(!raf) raf=requestAnimationFrame(frame);
  }
  function invalidate(){layoutPending=true;wake();}
  function ease(x){return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;}
  function paint(m){
    var im=clamp((m-0.3)/0.62);im=im*im*(3-2*im);
    var opacity=im.toFixed(3),filter=im<1?'blur('+((1-im)*9).toFixed(1)+'px)':'';
    if(opacity!==lastOpacity){img.style.opacity=opacity;lastOpacity=opacity;}
    if(filter!==lastFilter){img.style.filter=filter;lastFilter=filter;}
    if(m<=0||m>=1){if(!canvasEmpty) g.clearRect(0,0,W,CH);canvasEmpty=true;return;}
    var dot=Math.max(MW/210*0.95,0.9),show=Math.min(m/0.15,1);
    g.clearRect(0,0,W,CH);canvasEmpty=false;
    var count=W<768?Math.min(P.length,800):P.length;
    for(var i=0;i<count;i++){
      var p=P[i],c=ease(clamp((m-p.d*0.36)/0.6)),free=1-c;
      /* idle drift for free dots: two slow waves per axis (periods 2 to 20 s), deeper dots move more, so the swarm keeps breathing while the page is still */
      var wx=(Math.sin(time*0.9+p.ph)*9+Math.sin(time*0.37+p.ph*2.3)*6)*p.z*free, wy=(Math.cos(time*0.7+p.ph*1.7)*7+Math.sin(time*0.29+p.ph*3.1)*5)*p.z*free;
      var sx=p.hx*W+wx,sy=p.hy*CH+(1-m)*p.z*140+wy;
      var tx=L+p.tx*MW,ty=T+p.ty*MH,bend=Math.sin(c*Math.PI)*p.sw*W*0.08;
      var x=sx+(tx-sx)*c+bend,y=sy+(ty-sy)*c-Math.abs(bend)*0.3;
      var tw=1-0.3*free*(0.5+0.5*Math.sin(time*1.4+p.ph*3));
      var a=Math.min(0.3+0.55*p.z+0.3*c,1)*tw*show*(1-c*c*c*c),rad=(0.9+2.1*p.z)*free+dot*c;
      if(a<0.01) continue;
      var k=p.s===p.c?1:clamp((c-0.35)/0.5);
      if(k<1){g.globalAlpha=a*(1-k);g.fillStyle=PAL[p.s];g.beginPath();g.arc(x,y,rad,0,6.283);g.fill();}
      if(k>0){g.globalAlpha=a*k;g.fillStyle=PAL[p.c];g.beginPath();g.arc(x,y,rad,0,6.283);g.fill();}
    }
    g.globalAlpha=1;
  }
  function frame(ts){
    raf=0;
    if(document.hidden||motion.matches){last=0;return;}
    if(layoutPending) measure();
    var goal=target();
    if(!visible()){progress=goal;last=0;return;}
    var dt=last?Math.min((ts-last)/1000,0.1):1/60;last=ts;time+=dt;
    if(progress<0) progress=goal;
    progress+=(goal-progress)*(1-Math.exp(-dt*2.2));
    if(Math.abs(goal-progress)<0.0015) progress=goal;
    paint(progress);
    /* keep drifting while free dots are visible; sleep only before they appear or once the logo is complete */
    if(progress!==goal||(progress>0&&progress<1)) raf=requestAnimationFrame(frame);else last=0;
  }
  function start(){
    if(ready||motion.matches||!img.naturalWidth) return;
    cv=document.createElement('canvas');g=cv.getContext&&cv.getContext('2d');
    if(!g||!build()) return;
    cv.className='starfield';cv.setAttribute('aria-hidden','true');
    document.body.appendChild(cv);ready=true;
    /* Apply the first opacity before the class, avoiding a flash of the image. */
    measure();progress=target();paint(progress);
    document.documentElement.classList.add('stars-on');
    wake();
  }
  function motionChanged(){
    stop();
    if(motion.matches){
      document.documentElement.classList.remove('stars-on');img.style.opacity='';img.style.filter='';
      lastOpacity='';lastFilter='';if(cv) cv.style.display='none';
    }else if(ready){
      cv.style.display='';progress=-1;measure();progress=target();paint(progress);
      document.documentElement.classList.add('stars-on');wake();
    }else start();
  }
  window.addEventListener('scroll',wake,{passive:true});
  window.addEventListener('resize',invalidate,{passive:true});
  window.addEventListener('pageshow',invalidate);
  document.addEventListener('visibilitychange',function(){if(document.hidden) stop();else invalidate();});
  /* Images/fonts above the section can shift it long after initial rendering. */
  document.addEventListener('load',invalidate,true);
  if(window.ResizeObserver){var observer=new ResizeObserver(invalidate);observer.observe(document.body);observer.observe(band);observer.observe(mark);}
  if(document.fonts&&document.fonts.ready) document.fonts.ready.then(invalidate);
  if(motion.addEventListener) motion.addEventListener('change',motionChanged);else if(motion.addListener) motion.addListener(motionChanged);
  img.loading='eager';if(img.complete&&img.naturalWidth) start();else img.addEventListener('load',start,{once:true});
})();
