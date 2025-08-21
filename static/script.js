/**
 * Minimal utility toast
 */
function toast(msg, dur = 2500) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), dur);
}

/**
 * PHOTO GRID MODULE (registration)
 * - Adds up to 20 slots
 * - Each slot opens camera / picker
 * - Preview + Retake + Remove
 * - All inputs share name="photos" (server renames p1..p20)
 */
document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("photoGrid");
  const inputsWrap = document.getElementById("fileInputs");
  const addBtn = document.getElementById("addPhotoBtn");
  const MAX = 20;

  if (grid && addBtn && inputsWrap) {
    let count = 0;

    function relabel() {
      [...grid.children].forEach((slot, i) => {
        const badge = slot.querySelector(".badge");
        if (badge) badge.textContent = `p${i + 1}`;
      });
    }

    function createSlot() {
      if (count >= MAX) {
        toast("You can only add up to 20 photos.");
        return;
      }
      count++;

      // Hidden file input
      const input = document.createElement("input");
      input.type = "file";
      input.name = "photos";              // important for Flask getlist('photos')
      input.accept = "image/*";
      input.capture = "environment";      // hint for mobile camera
      input.style.display = "none";
      inputsWrap.appendChild(input);

      // Visual slot
      const slot = document.createElement("div");
      slot.className = "slot fade-in-up";

      const badge = document.createElement("div");
      badge.className = "badge";
      badge.textContent = `p${count}`;

      const prompt = document.createElement("div");
      prompt.innerHTML = `＋ Tap to add`;

      const img = document.createElement("img");
      img.style.display = "none";

      const toolbar = document.createElement("div");
      toolbar.className = "toolbar";

      const btnRetake = document.createElement("button");
      btnRetake.type = "button";
      btnRetake.className = "btn ghost";
      btnRetake.textContent = "Retake";

      const btnRemove = document.createElement("button");
      btnRemove.type = "button";
      btnRemove.className = "btn ghost";
      btnRemove.textContent = "Remove";

      toolbar.appendChild(btnRetake);
      toolbar.appendChild(btnRemove);
      toolbar.style.display = "none";

      slot.appendChild(badge);
      slot.appendChild(prompt);
      slot.appendChild(img);
      slot.appendChild(toolbar);
      grid.appendChild(slot);

      // Interactions
      const openPicker = () => input.click();

      slot.addEventListener("click", (e) => {
        // Avoid slot click when pressing buttons
        if (e.target === btnRetake || e.target === btnRemove) return;
        openPicker();
      });

      input.addEventListener("change", () => {
        if (input.files && input.files[0]) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            img.src = ev.target.result;
            img.style.display = "block";
            prompt.style.display = "none";
            toolbar.style.display = "flex";
          };
          reader.readAsDataURL(input.files[0]);
        }
      });

      btnRetake.addEventListener("click", () => openPicker());

      btnRemove.addEventListener("click", () => {
        // Remove both slot and its input
        slot.remove();
        input.remove();
        count--;
        relabel();
      });
    }

    // First slot by default
    createSlot();
    addBtn.addEventListener("click", createSlot);
  }

  /**
   * AJAX submit: Registration
   */
  const regForm = document.getElementById("regForm");
  if (regForm) {
    regForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(regForm);

      // Validate there is at least one photo
      const hasPhoto = [...fd.keys()].includes("photos");
      if (!hasPhoto) {
        toast("Please add at least one photo.");
        return;
      }

      try {
        const res = await fetch(regForm.action, { method: "POST", body: fd });
        const data = await res.json();
        if (data.status === "success") {
          toast("Registration successful.");
          regForm.reset();
          // Optional: simple reload to reset UI
          setTimeout(() => window.location.reload(), 800);
        } else {
          toast(data.message || "Error while submitting.");
        }
      } catch (err) {
        toast("Network error. Please try again.");
      }
    });
  }

  /**
   * AJAX submit: Missing report
   */
  const missingForm = document.getElementById("missingForm");
  if (missingForm) {
    missingForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(missingForm);

      // Normalize member_code to be like 'p2' (no extension needed)
      let code = (fd.get("member_code") || "").trim().toLowerCase();
      if (!code) { toast("Please enter member code like p2."); return; }
      fd.set("member_code", code);

      try {
        const res = await fetch(missingForm.action, { method: "POST", body: fd });
        const data = await res.json();
        if (data.status === "success") {
          toast("Missing report submitted.");
          missingForm.reset();
        } else {
          toast(data.message || "Error while submitting.");
        }
      } catch (err) {
        toast("Network error. Please try again.");
      }
    });
  }
});
