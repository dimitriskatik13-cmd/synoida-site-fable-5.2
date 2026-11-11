/* ΣΥΝΟΙΔΑ, Αρχική: η κορύφωση. Κουκκίδες στα χρώματα του λογοτύπου μαζεύονται από όλη την οθόνη και γίνονται το αυθεντικό λογότυπο.
   Η ενότητα #logo-reveal «κρατά» την οθόνη (sticky σκηνή .hx-stage) για περίπου δύο ύψη οθόνης και η κύλιση οδηγεί την κίνηση:
     πρόοδος 0 έως 0,78   οι κουκκίδες εμφανίζονται, ταξιδεύουν και κλειδώνουν στο λογότυπο
     από 0,78 και μετά     το λογότυπο είναι καθαρό, ο τίτλος και το κουμπί ανεβαίνουν (κλάση is-formed) και η οθόνη «κρατά»
   Η γεωμετρία μετριέται μόνο όταν αλλάζει η διάταξη. Όσο υπάρχουν ελεύθερες κουκκίδες αιωρούνται ήρεμα ακόμη και χωρίς κύλιση.
   Ο καμβάς κοιμάται εκτός οθόνης, πριν εμφανιστούν οι κουκκίδες και όταν ολοκληρωθεί το λογότυπο.
   Με «μείωση κίνησης» ή εξοικονόμηση δεδομένων δεν δημιουργείται καμβάς: μένει το λογότυπο και το κείμενο, χωρίς καρφίτσωμα. */
(function(){
  var band=document.getElementById('logo-reveal'), stage=band&&band.querySelector('.hx-stage'), mark=stage&&stage.querySelector('.hx-mark'), img=mark&&mark.querySelector('img');
  if(!mark||!img||!window.requestAnimationFrame) return;
  if(navigator.connection&&navigator.connection.saveData) return;
  var FORMED=0.78;   /* το κλάσμα της κύλισης της ενότητας στο οποίο το λογότυπο έχει ολοκληρωθεί */
  var motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  var cv=null,g=null,ready=false,raf=0,layoutPending=true;
  var W=0,CH=0,dpr=1,P=[],vh=0,bandTop=0,bandH=1,L=0,T=0,MW=0,MH=0,formed=false;
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
    var b=band.getBoundingClientRect(),st=stage.getBoundingClientRect(),r=mark.getBoundingClientRect();
    var w=Math.max(1,Math.round(st.width)),h=Math.max(1,Math.round(st.height));
    var density=Math.min(window.devicePixelRatio||1,w<768?1.25:1.5,Math.sqrt(2500000/(w*h)));
    vh=window.innerHeight;bandTop=b.top+window.scrollY;bandH=b.height;
    L=r.left-st.left;T=r.top-st.top;MW=r.width;MH=r.height;          /* η θέση του λογοτύπου μέσα στη σκηνή: σταθερή όσο η σκηνή είναι καρφωμένη */
    if(W!==w||CH!==h||dpr!==density){
      W=w;CH=h;dpr=density;
      cv.width=Math.max(1,Math.round(w*dpr));cv.height=Math.max(1,Math.round(h*dpr));
      g.setTransform(dpr,0,0,dpr,0,0);canvasEmpty=true;
    }
    layoutPending=false;
  }
  /* Η κύλιση ξεκινά να μετρά μισή οθόνη πριν καρφωθεί η σκηνή (οι κουκκίδες φαίνονται καθώς πλησιάζει) και τελειώνει στο FORMED. */
  function target(){var lead=vh*0.5,travel=Math.max(bandH-vh+lead,1);return clamp((window.scrollY-(bandTop-lead))/travel/FORMED);}
  function visible(){var top=bandTop-window.scrollY;return top<vh&&top+bandH>0;}
  function wake(){
    if(!ready||motion.matches||document.hidden) return;
    if(!layoutPending&&!visible()){
      progress=target();setFormed(progress>=0.93);stop();return;      /* εκτός οθόνης: συγχρονισμός χωρίς ζωγραφική */
    }
    if(!raf) raf=requestAnimationFrame(frame);
  }
  function invalidate(){layoutPending=true;wake();}
  function ease(x){return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;}
  function setFormed(on){if(on!==formed){formed=on;stage.classList.toggle('is-formed',on);}}
  function paint(m){
    setFormed(m>=0.93);   /* το λογότυπο είναι πια καθαρό: ανεβαίνει το κείμενο */
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
    cv.className='hx-stars';cv.setAttribute('aria-hidden','true');
    stage.insertBefore(cv,stage.firstChild);ready=true;
    /* Η κλάση stars-on καρφώνει τη σκηνή (CSS)· μετράμε αφού εφαρμοστεί, ώστε η γεωμετρία να είναι η τελική. */
    document.documentElement.classList.add('stars-on');
    measure();progress=target();paint(progress);
    wake();
  }
  function motionChanged(){
    stop();
    if(motion.matches){
      document.documentElement.classList.remove('stars-on');img.style.opacity='';img.style.filter='';setFormed(false);
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
  if(window.ResizeObserver){var observer=new ResizeObserver(invalidate);observer.observe(document.body);observer.observe(band);observer.observe(stage);observer.observe(mark);}
  if(document.fonts&&document.fonts.ready) document.fonts.ready.then(invalidate);
  if(motion.addEventListener) motion.addEventListener('change',motionChanged);else if(motion.addListener) motion.addListener(motionChanged);
  img.loading='eager';if(img.complete&&img.naturalWidth) start();else img.addEventListener('load',start,{once:true});
})();
