const figmaUrlInput = document.getElementById("figma-url");
const fileInput = document.getElementById("file-input");
const detailLevelSelect = document.getElementById("detail-level");
const generateBtn = document.getElementById("generate-btn");
const downloadBtn = document.getElementById("download-btn");
const resultBox = document.getElementById("result-box");
const resultSection = document.getElementById("result-section");
const tabUrl = document.getElementById("tab-url");
const tabFile = document.getElementById("tab-file");
const sectionUrl = document.getElementById("section-url");
const sectionFile = document.getElementById("section-file");

let lastResult = null;
let currentMode = "url";

// --- Tab switching ---

tabUrl.addEventListener("click", () => {
  currentMode = "url";
  tabUrl.classList.add("tab--active");
  tabUrl.setAttribute("aria-selected", "true");
  tabFile.classList.remove("tab--active");
  tabFile.setAttribute("aria-selected", "false");
  sectionUrl.hidden = false;
  sectionFile.hidden = true;
});

tabFile.addEventListener("click", () => {
  currentMode = "file";
  tabFile.classList.add("tab--active");
  tabFile.setAttribute("aria-selected", "true");
  tabUrl.classList.remove("tab--active");
  tabUrl.setAttribute("aria-selected", "false");
  sectionUrl.hidden = true;
  sectionFile.hidden = false;
});

// --- Result rendering ---

const showResult = () => {
  resultSection.hidden = false;
};

const renderStatus = (message, isError = false) => {
  showResult();
  resultBox.textContent = message;
  resultBox.classList.toggle("result__box--error", isError);
};

const renderMarkdown = (markdown) => {
  showResult();
  resultBox.classList.remove("result__box--error");
  resultBox.textContent = markdown;
};

// --- Generate ---

generateBtn.addEventListener("click", async () => {
  generateBtn.disabled = true;
  renderStatus("Генерация...", false);

  try {
    if (currentMode === "url") {
      await generateFromUrl();
    } else {
      await generateFromFile();
    }
  } finally {
    generateBtn.disabled = false;
  }
});

async function generateFromUrl() {
  const figmaUrl = figmaUrlInput.value.trim();
  if (!figmaUrl) {
    renderStatus("Укажите ссылку на макет Figma.", true);
    return;
  }

  const payload = {
    figma_url: figmaUrl,
    figma_token: "",
    language: "ru",
    detail_level: detailLevelSelect.value,
  };

  try {
    const response = await fetch("/guide/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || "Ошибка генерации");
    }

    const data = await response.json();
    lastResult = data;
    renderMarkdown(data.markdown || "Результат пустой.");
  } catch (error) {
    renderStatus(error.message, true);
  }
}

async function generateFromFile() {
  const file = fileInput.files[0];
  if (!file) {
    renderStatus("Выберите файл.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("language", "ru");
  formData.append("detail_level", detailLevelSelect.value);


  try {
    const response = await fetch("/guide/upload", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || "Ошибка генерации");
    }

    const data = await response.json();
    lastResult = data;
    renderMarkdown(data.markdown || "Результат пустой.");
  } catch (error) {
    renderStatus(error.message, true);
  }
}

// --- Download ---

downloadBtn.addEventListener("click", () => {
  if (!lastResult) {
    renderStatus("Сначала сгенерируйте результат.", true);
    return;
  }

  const blob = new Blob([lastResult.markdown || ""], { type: "text/markdown" });

  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "guide.md";
  link.click();
  URL.revokeObjectURL(link.href);
});
