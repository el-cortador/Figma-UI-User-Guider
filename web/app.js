const figmaUrlInput = document.getElementById("figma-url");
const detailLevelSelect = document.getElementById("detail-level");
const audienceSelect = document.getElementById("audience");
const generateBtn = document.getElementById("generate-btn");
const downloadBtn = document.getElementById("download-btn");
const resultBox = document.getElementById("result-box");

let lastResult = null;

const renderStatus = (message, isError = false) => {
  resultBox.textContent = message;
  resultBox.classList.toggle("result__box--error", isError);
};

const renderMarkdown = (markdown) => {
  resultBox.classList.remove("result__box--error");
  resultBox.textContent = markdown;
};

generateBtn.addEventListener("click", async () => {
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
    audience: audienceSelect.value,
  };

  renderStatus("Генерация...", false);

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
});

downloadBtn.addEventListener("click", () => {
  if (!lastResult) {
    renderStatus("Сначала сгенерируйте результат.", true);
    return;
  }

  const blob = new Blob(
    [
      "# Руководство\n\n",
      lastResult.markdown || "",
      "\n\n```json\n",
      JSON.stringify(lastResult.guide_json || {}, null, 2),
      "\n```\n",
    ],
    { type: "text/markdown" }
  );

  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "guide.md";
  link.click();
  URL.revokeObjectURL(link.href);
});
