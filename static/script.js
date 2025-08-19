
// ====== NOTIFICATIONS (with thumbnails) ======
const Notif = (() => {
  function fetchAndShow(listEl){
    fetch('/notifications')
      .then(r => r.json())
      .then(data => {
        listEl.innerHTML = '';
        if (!data.length){
          listEl.innerHTML = '<div class="muted">No notifications yet.</div>';
          return;
        }
        data.forEach(item => {
          const card = document.createElement('div');
          card.className = 'thumb';
          card.innerHTML = `
            <img src="${item.url}" alt="${item.file}"/>
            <div class="meta">
              <div class="phone">${item.phone}</div>
              <div class="file">${item.file}</div>
              <div class="file" style="font-size:11px">${new Date(item.timestamp).toLocaleString()}</div>
            </div>
          `;
          listEl.appendChild(card);
        });
      })
      .catch(err => {
        listEl.innerHTML = '<div class="muted">Failed to load notifications.</div>';
        console.error(err);
      });
  }
  function bind(){
    const btn = document.getElementById('notif-btn');
    const modal = document.getElementById('notif-modal');
    const list = document.getElementById('notif-list');
    const close = document.getElementById('close-notif');
    if (!btn || !modal) return;
    btn.addEventListener('click', (e)=>{ e.preventDefault(); modal.classList.remove('hidden'); fetchAndShow(list); });
    close.addEventListener('click', ()=> modal.classList.add('hidden'));
    modal.addEventListener('click', (ev)=>{ if (ev.target === modal) modal.classList.add('hidden'); });
  }
  return { init: bind };
})();

// ====== Image Capture for Registration ======
let cameraInput;
const RegForm = (() => {
  const MAX = 20;
  let container;
  let captured = new Array(MAX);

  function createSlot(i, file){
    const slot = document.createElement('div');
    slot.className = 'slot';
    slot.dataset.index = i;
    if (file){
      const url = URL.createObjectURL(file);
      slot.innerHTML = `<img src="${url}"><span class="tag">p${i}</span>`;
      const actions = document.createElement('div');
      actions.className = 'slot-actions';
      const remove = document.createElement('button'); remove.className='small-btn'; remove.textContent='Remove';
      remove.addEventListener('click', (e)=>{ e.stopPropagation(); captured[i-1]=undefined; render(); });
      const retake = document.createElement('button'); retake.className='small-btn'; retake.textContent='Retake';
      retake.addEventListener('click', (e)=>{ e.stopPropagation(); openCamera(slot); });
      actions.appendChild(remove); actions.appendChild(retake);
      slot.appendChild(actions);
    } else {
      slot.classList.add('slot-empty');
      slot.innerHTML = `<div class="plus">+ p${i}</div>`;
      slot.addEventListener('click', ()=> openCamera(slot));
    }
    return slot;
  }

  function openCamera(slot){
    if (!cameraInput){
      cameraInput = document.createElement('input');
      cameraInput.type = 'file';
      cameraInput.accept = 'image/*';
      cameraInput.capture = 'environment';
      cameraInput.style.display = 'none';
      document.body.appendChild(cameraInput);
    }
    const idx = parseInt(slot.dataset.index,10);
    cameraInput.onchange = () => {
      const f = cameraInput.files && cameraInput.files[0];
      if (!f) return;
      captured[idx-1] = f;
      cameraInput.value = '';
      render();
    };
    cameraInput.click();
  }

  function render(){
    container.innerHTML = '';
    for (let i=1;i<=MAX;i++){
      container.appendChild(createSlot(i, captured[i-1]));
    }
  }

  function bindSubmit(){
    const form = document.getElementById('reg-form');
    form.addEventListener('submit', (e)=>{
      e.preventDefault();
      const fd = new FormData(form);
      let any = false;
      for (let i=0;i<MAX;i++){
        const f = captured[i];
        if (f){
          any = True;
          const ext = (f.name.split('.').pop() || 'jpeg').toLowerCase();
          const filename = `p${i+1}.${ext}`;
          fd.append('family_photos', new File([f], filename, {type: f.type || 'image/jpeg'}), filename);
        }
      }
      if (!any){
        alert('Please add at least one photo.');
        return;
      }
      fetch(form.action, { method:'POST', body: fd })
        .then(r => { if (r.redirected) window.location = r.url; else return r.text().then(alert); })
        .catch(err => alert('Upload failed: ' + err));
    });
  }

  function init(){
    container = document.getElementById('camera-slots');
    if (!container) return;
    render();
    bindSubmit();
  }

  return { init };
})();

document.addEventListener('DOMContentLoaded', ()=>{
  Notif.init();
  RegForm.init();
});
