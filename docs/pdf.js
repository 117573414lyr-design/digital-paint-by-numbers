/* V110 minimal PDF writer: vector effect, numbered linework and palette pages. */
(function(){
  'use strict';
  const A4L={w:842,h:595,margin:36};
  const esc=s=>String(s).replace(/\\/g,'\\\\').replace(/\(/g,'\\(').replace(/\)/g,'\\)');
  const n=v=>Number(v).toFixed(3).replace(/\.000$/,'');
  function imageTransform(width,height){
    const maxW=A4L.w-A4L.margin*2,maxH=A4L.h-A4L.margin*2;
    const scale=Math.min(maxW/width,maxH/height);
    return {scale,ox:(A4L.w-width*scale)/2,oy:(A4L.h-height*scale)/2};
  }
  function text(x,y,size,value){return `BT /F1 ${n(size)} Tf ${n(x)} ${n(y)} Td (${esc(value)}) Tj ET\n`;}
  function page1(data){
    const {width:w,height:h,colorIndex,palette}=data,t=imageTransform(w,h);
    let out='q\n';
    for(let y=0;y<h;y++){
      let x=0;
      while(x<w){
        const ci=colorIndex[y*w+x];let x2=x+1;
        while(x2<w&&colorIndex[y*w+x2]===ci)x2++;
        const rgb=palette[ci].rgb,r=rgb[0]/255,g=rgb[1]/255,b=rgb[2]/255;
        const px=t.ox+x*t.scale,py=t.oy+(h-y-1)*t.scale,pw=(x2-x)*t.scale,ph=t.scale+0.02;
        out+=`${n(r)} ${n(g)} ${n(b)} rg ${n(px)} ${n(py)} ${n(pw)} ${n(ph)} re f\n`;
        x=x2;
      }
    }
    out+='Q\n';
    out+=text(36,565,10,'Paint by Numbers - Page 1 / Effect');
    return out;
  }
  function page2(data){
    const {width:w,height:h,colorIndex,palette,regions,labelArea,labelPoint}=data,t=imageTransform(w,h);
    let out='q\n0.4 1 1 1 K 0.1 w 1 J 1 j\n';
    for(let y=0;y<h-1;y++){
      for(let x=0;x<w-1;x++){
        const p=y*w+x;
        if(colorIndex[p]!==colorIndex[p+1]){
          const xx=t.ox+(x+1)*t.scale,y1=t.oy+(h-y)*t.scale,y2=t.oy+(h-y-1)*t.scale;
          out+=`${n(xx)} ${n(y1)} m ${n(xx)} ${n(y2)} l S\n`;
        }
        if(colorIndex[p]!==colorIndex[p+w]){
          const yy=t.oy+(h-y-1)*t.scale,x1=t.ox+x*t.scale,x2=t.ox+(x+1)*t.scale;
          out+=`${n(x1)} ${n(yy)} m ${n(x2)} ${n(yy)} l S\n`;
        }
      }
    }
    out+='Q\n';
    for(const r of regions){
      if(r.area<labelArea)continue;
      const pt=labelPoint(r),span=Math.min(r.maxx-r.minx,r.maxy-r.miny),fs=span>34?8:span>20?6:4.2;
      const tx=t.ox+pt.x*t.scale,ty=t.oy+(h-pt.y)*t.scale;
      out+=text(tx-fs*.6,ty-fs*.35,fs,palette[r.color].id);
    }
    out+=text(36,565,10,'Paint by Numbers - Page 2 / Numbered Linework');
    return out;
  }
  function page3(data){
    const {palette}=data;
    let out=text(36,555,16,'Paint by Numbers - Page 3 / Palette');
    const cols=4,cellW=185,cellH=55,startX=42,startY=515;
    palette.forEach((p,i)=>{
      const col=i%cols,row=Math.floor(i/cols),x=startX+col*cellW,y=startY-row*cellH;
      const rgb=p.rgb,r=rgb[0]/255,g=rgb[1]/255,b=rgb[2]/255;
      out+=`${n(r)} ${n(g)} ${n(b)} rg ${n(x)} ${n(y-25)} 36 26 re f\n`;
      out+='0 0 0 RG 0.4 w '+`${n(x)} ${n(y-25)} 36 26 re S\n`;
      out+=text(x+44,y-10,9,p.id);
      out+=text(x+44,y-22,7,`RGB ${rgb[0]}/${rgb[1]}/${rgb[2]}`);
    });
    return out;
  }
  function buildPdf(streams){
    const objects=[];
    const add=s=>{objects.push(s);return objects.length;};
    const font=add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
    const contents=streams.map(s=>add(`<< /Length ${s.length} >>\nstream\n${s}endstream`));
    const pageIds=[];
    const pagesPlaceholder=objects.length+1;
    add('PAGES_PLACEHOLDER');
    for(const contentId of contents){
      pageIds.push(add(`<< /Type /Page /Parent ${pagesPlaceholder} 0 R /MediaBox [0 0 ${A4L.w} ${A4L.h}] /Resources << /Font << /F1 ${font} 0 R >> >> /Contents ${contentId} 0 R >>`));
    }
    objects[pagesPlaceholder-1]=`<< /Type /Pages /Kids [${pageIds.map(id=>`${id} 0 R`).join(' ')}] /Count ${pageIds.length} >>`;
    const catalog=add(`<< /Type /Catalog /Pages ${pagesPlaceholder} 0 R >>`);
    let pdf='%PDF-1.4\n%PBNV110\n',offsets=[0];
    for(let i=0;i<objects.length;i++){
      offsets.push(pdf.length);
      pdf+=`${i+1} 0 obj\n${objects[i]}\nendobj\n`;
    }
    const xref=pdf.length;
    pdf+=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n`;
    for(let i=1;i<=objects.length;i++)pdf+=String(offsets[i]).padStart(10,'0')+' 00000 n \n';
    pdf+=`trailer\n<< /Size ${objects.length+1} /Root ${catalog} 0 R >>\nstartxref\n${xref}\n%%EOF`;
    return new Blob([pdf],{type:'application/pdf'});
  }
  window.PBNPdf={generate(data){return buildPdf([page1(data),page2(data),page3(data)]);}};
})();
