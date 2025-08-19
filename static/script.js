document.addEventListener("DOMContentLoaded", () => {
  const photoSlots = document.getElementById("photoSlots");
  const addPhotoBtn = document.getElementById("addPhoto");
  let photoCount = 0;
  const maxPhotos = 20;

  function addPhotoSlot() {
    if (photoCount >= maxPhotos) return;
    photoCount++;

    const slot = document.createElement("div");
    slot.className = "photo-slot";

    const label = document.createElement("label");
    label.textContent = `Photo p${photoCount}`;

    const input = document.createElement("input");
    input.type = "file";
    input.name = `photo${photoCount}`;
    input.accept = "image/*";
    input.capture = "environment";

    const imgPreview = document.createElement("img");
    imgPreview.style.maxWidth = "100%";
    imgPreview.style.display = "none";

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Remove";
    removeBtn.style.display = "none";

    input.addEventListener("change", () => {
      if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = e => {
          imgPreview.src = e.target.result;
          imgPreview.style.display = "block";
          removeBtn.style.display = "block";
        };
        reader.readAsDataURL(input.files[0]);
      }
    });

    removeBtn.addEventListener("click", () => {
      slot.remove();
      photoCount--;
    });

    slot.appendChild(label);
    slot.appendChild(input);
    slot.appendChild(imgPreview);
    slot.appendChild(removeBtn);

    photoSlots.appendChild(slot);
  }

  addPhotoBtn.addEventListener("click", addPhotoSlot);

  addPhotoSlot(); // first slot
});
