/**
 * ThoraxAI Clinical Workspace Interactive Controller (PRD v2.0)
 * Implements:
 *  - FR-03: Chest X-ray Upload validation & live preview
 *  - FR-05: Side-by-Side Analysis Interface controls
 *  - FR-06: Interactive X-ray Viewer (Zoom slider, pan, Desktop Hover-to-Zoom Loupe, Reset)
 *  - FR-07: Report-Grounded Contextual Chatbot with Markdown formatting
 *  - FR-12: Ownership-verified Analysis Deletion with confirmation modal
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Lightweight Markdown-to-HTML Renderer for Chatbot Responses
  // ---------------------------------------------------------------------------
  function renderMarkdown(mdText) {
    if (!mdText) return "";
    let html = mdText
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Code spans
    html = html.replace(/`([^`]+)`/g, '<code style="background:#F1F5F9;padding:1px 5px;border-radius:4px;font-family:var(--font-mono);font-size:0.82em;color:#0F172A;">$1</code>');
    // Headings
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote style="margin:0.4rem 0;padding:0.45rem 0.75rem;border-left:3px solid #0284C7;background:#F0F9FF;color:#1E293B;border-radius:0 4px 4px 0;">$1</blockquote>');
    // Bold & Italics
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

    // Process lines into paragraphs and lists
    const lines = html.split("\n");
    let out = [];
    let inUl = false;
    let inOl = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) {
        if (inUl) { out.push("</ul>"); inUl = false; }
        if (inOl) { out.push("</ol>"); inOl = false; }
        continue;
      }
      if (line.startsWith("- ") || line.startsWith("• ")) {
        if (inOl) { out.push("</ol>"); inOl = false; }
        if (!inUl) { out.push("<ul>"); inUl = true; }
        out.push("<li>" + line.substring(2) + "</li>");
      } else if (/^\d+\.\s+/.test(line)) {
        if (inUl) { out.push("</ul>"); inUl = false; }
        if (!inOl) { out.push("<ol>"); inOl = true; }
        out.push("<li>" + line.replace(/^\d+\.\s+/, "") + "</li>");
      } else {
        if (inUl) { out.push("</ul>"); inUl = false; }
        if (inOl) { out.push("</ol>"); inOl = false; }
        if (line.startsWith("<h3>") || line.startsWith("<h4>") || line.startsWith("<blockquote")) {
          out.push(line);
        } else {
          out.push("<p>" + line + "</p>");
        }
      }
    }
    if (inUl) out.push("</ul>");
    if (inOl) out.push("</ol>");
    return out.join("");
  }

  // Apply markdown rendering to all initial server-rendered assistant messages
  function formatInitialChatMessages() {
    document.querySelectorAll(".js-markdown-content").forEach(function (el) {
      const raw = el.getAttribute("data-raw") || el.textContent;
      el.innerHTML = renderMarkdown(raw);
    });
    const chatStream = document.getElementById("chatMessagesStream");
    if (chatStream) {
      chatStream.scrollTop = chatStream.scrollHeight;
    }
  }

  // ---------------------------------------------------------------------------
  // FR-06: Interactive X-ray Viewer (Zoom Slider, Pan, Hover-to-Zoom Loupe)
  // ---------------------------------------------------------------------------
  function initXrayViewer() {
    const viewport = document.getElementById("pacsViewportStage");
    const wrapper = document.getElementById("xrayImageWrapper");
    const img = document.getElementById("xrayMainImage");
    const zoomSlider = document.getElementById("xrayZoomSlider");
    const zoomBadge = document.getElementById("xrayZoomBadge");
    const btnZoomIn = document.getElementById("btnZoomIn");
    const btnZoomOut = document.getElementById("btnZoomOut");
    const btnResetZoom = document.getElementById("btnResetZoom");
    const loupe = document.getElementById("hoverZoomLoupe");
    const loupeTag = document.getElementById("loupeMagTag");
    const btnToggleLoupe = document.getElementById("btnToggleLoupe");
    const btnLoupeMag = document.getElementById("btnLoupeMag");
    const btnModeOrig = document.getElementById("btnModeOrig");
    const btnModeClahe = document.getElementById("btnModeClahe");
    const btnInvert = document.getElementById("btnInvertXray");

    if (!viewport || !img || !zoomSlider) return;

    let currentZoom = 100; // percentage (100% - 350%)
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;

    let loupeEnabled = true;
    let loupeFactor = 2.5;
    const loupeFactors = [2.0, 2.5, 3.5];
    let loupeFactorIdx = 1;

    function clampPan() {
      if (currentZoom <= 100) {
        panX = 0;
        panY = 0;
        return;
      }
      const maxOffset = ((currentZoom - 100) / 100) * 190;
      panX = Math.max(-maxOffset, Math.min(maxOffset, panX));
      panY = Math.max(-maxOffset, Math.min(maxOffset, panY));
    }

    function applyTransform() {
      clampPan();
      const scale = currentZoom / 100;
      wrapper.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
      zoomSlider.value = String(currentZoom);
      if (zoomBadge) {
        zoomBadge.textContent = `${currentZoom}%`;
      }
      viewport.style.cursor = currentZoom > 100 ? (isDragging ? "grabbing" : "grab") : (loupeEnabled ? "crosshair" : "default");
    }

    function setZoom(newZoom) {
      currentZoom = Math.max(100, Math.min(350, Math.round(newZoom)));
      applyTransform();
    }

    zoomSlider.addEventListener("input", function (e) {
      setZoom(parseInt(e.target.value, 10) || 100);
    });

    if (btnZoomIn) {
      btnZoomIn.addEventListener("click", function () {
        setZoom(currentZoom + 25);
      });
    }

    if (btnZoomOut) {
      btnZoomOut.addEventListener("click", function () {
        setZoom(currentZoom - 25);
      });
    }

    if (btnResetZoom) {
      btnResetZoom.addEventListener("click", function () {
        currentZoom = 100;
        panX = 0;
        panY = 0;
        img.classList.remove("invert-filter");
        if (btnInvert) btnInvert.classList.remove("active");
        applyTransform();
      });
    }

    // Mouse wheel subtle zoom inside viewport
    viewport.addEventListener("wheel", function (e) {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 15 : -15;
      setZoom(currentZoom + delta);
    }, { passive: false });

    // Drag to pan when zoomed in
    viewport.addEventListener("mousedown", function (e) {
      if (currentZoom <= 100) return;
      isDragging = true;
      dragStartX = e.clientX - panX;
      dragStartY = e.clientY - panY;
      if (loupe) loupe.style.display = "none";
      applyTransform();
    });

    window.addEventListener("mousemove", function (e) {
      if (!isDragging) return;
      panX = e.clientX - dragStartX;
      panY = e.clientY - dragStartY;
      applyTransform();
    });

    window.addEventListener("mouseup", function () {
      if (isDragging) {
        isDragging = false;
        applyTransform();
      }
    });

    // Touch support for mobile inspection (FR-06)
    let touchStartDist = 0;
    let touchStartZoom = 100;
    viewport.addEventListener("touchstart", function (e) {
      if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        touchStartDist = Math.hypot(dx, dy);
        touchStartZoom = currentZoom;
      } else if (e.touches.length === 1 && currentZoom > 100) {
        isDragging = true;
        dragStartX = e.touches[0].clientX - panX;
        dragStartY = e.touches[0].clientY - panY;
      }
    }, { passive: true });

    viewport.addEventListener("touchmove", function (e) {
      if (e.touches.length === 2 && touchStartDist > 0) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        const ratio = dist / touchStartDist;
        setZoom(touchStartZoom * ratio);
      } else if (e.touches.length === 1 && isDragging) {
        panX = e.touches[0].clientX - dragStartX;
        panY = e.touches[0].clientY - dragStartY;
        applyTransform();
      }
    }, { passive: true });

    viewport.addEventListener("touchend", function () {
      isDragging = false;
      touchStartDist = 0;
    });

    // Desktop Hover-to-Zoom Loupe (FR-06)
    function updateLoupe(e) {
      if (!loupe || !loupeEnabled || isDragging) {
        if (loupe) loupe.style.display = "none";
        return;
      }
      const imgRect = img.getBoundingClientRect();
      const vpRect = viewport.getBoundingClientRect();

      // Check if pointer is inside the rendered chest X-ray image bounds
      if (
        e.clientX < imgRect.left ||
        e.clientX > imgRect.right ||
        e.clientY < imgRect.top ||
        e.clientY > imgRect.bottom
      ) {
        loupe.style.display = "none";
        return;
      }

      loupe.style.display = "block";
      const loupeW = loupe.offsetWidth || 176;
      const loupeH = loupe.offsetHeight || 176;

      // Relative position (0..1) inside the rendered image
      const relX = (e.clientX - imgRect.left) / imgRect.width;
      const relY = (e.clientY - imgRect.top) / imgRect.height;

      // Keep loupe within viewport boundaries so it never overflows or covers Panel B
      let leftPos = e.clientX - vpRect.left - loupeW / 2;
      let topPos = e.clientY - vpRect.top - loupeH / 2;
      leftPos = Math.max(6, Math.min(vpRect.width - loupeW - 6, leftPos));
      topPos = Math.max(6, Math.min(vpRect.height - loupeH - 6, topPos));

      loupe.style.left = `${leftPos}px`;
      loupe.style.top = `${topPos}px`;

      const bgW = imgRect.width * loupeFactor;
      const bgH = imgRect.height * loupeFactor;
      const bgPosX = -(relX * bgW - loupeW / 2);
      const bgPosY = -(relY * bgH - loupeH / 2);

      loupe.style.backgroundImage = `url('${img.src}')`;
      loupe.style.backgroundSize = `${bgW}px ${bgH}px`;
      loupe.style.backgroundPosition = `${bgPosX}px ${bgPosY}px`;
      loupe.style.filter = img.classList.contains("invert-filter") ? "invert(1) contrast(1.08)" : "none";
    }

    viewport.addEventListener("mousemove", updateLoupe);
    viewport.addEventListener("mouseleave", function () {
      if (loupe) loupe.style.display = "none";
    });

    if (btnToggleLoupe) {
      btnToggleLoupe.addEventListener("click", function () {
        loupeEnabled = !loupeEnabled;
        btnToggleLoupe.classList.toggle("active", loupeEnabled);
        btnToggleLoupe.textContent = loupeEnabled ? "Hover-to-Zoom: ON" : "Hover-to-Zoom: OFF";
        if (!loupeEnabled && loupe) loupe.style.display = "none";
        applyTransform();
      });
    }

    if (btnLoupeMag) {
      btnLoupeMag.addEventListener("click", function () {
        loupeFactorIdx = (loupeFactorIdx + 1) % loupeFactors.length;
        loupeFactor = loupeFactors[loupeFactorIdx];
        btnLoupeMag.textContent = `Lens: ${loupeFactor.toFixed(1)}×`;
        if (loupeTag) loupeTag.textContent = `${loupeFactor.toFixed(1)}× LOUPE`;
      });
    }

    // Switch between Original Upload and CLAHE Preprocessed Image
    if (btnModeOrig && btnModeClahe) {
      btnModeOrig.addEventListener("click", function () {
        const origUrl = img.getAttribute("data-orig-src");
        if (origUrl) img.src = origUrl;
        btnModeOrig.classList.add("active");
        btnModeClahe.classList.remove("active");
      });
      btnModeClahe.addEventListener("click", function () {
        const claheUrl = img.getAttribute("data-clahe-src");
        if (claheUrl) img.src = claheUrl;
        btnModeClahe.classList.add("active");
        btnModeOrig.classList.remove("active");
      });
    }

    if (btnInvert) {
      btnInvert.addEventListener("click", function () {
        img.classList.toggle("invert-filter");
        btnInvert.classList.toggle("active");
      });
    }

    applyTransform();
  }

  // ---------------------------------------------------------------------------
  // FR-03 & FR-04: Upload Validation, Image Preview & AI Inference Submission
  // ---------------------------------------------------------------------------
  function initUploadWorkflow() {
    const toggleUploadBtn = document.getElementById("btnShowUploader");
    const uploadStageCard = document.getElementById("uploadStageCard");
    const closeUploadBtn = document.getElementById("btnCloseUploader");
    const dropzone = document.getElementById("xrayDropzone");
    const fileInput = document.getElementById("xrayFileInput");
    const previewBox = document.getElementById("uploadPreviewBox");
    const previewImg = document.getElementById("uploadPreviewImg");
    const previewFilename = document.getElementById("uploadPreviewFilename");
    const previewMeta = document.getElementById("uploadPreviewMeta");
    const uploadErrorBox = document.getElementById("uploadErrorBox");
    const btnRunAnalysis = document.getElementById("btnRunAnalysis");
    const btnClearSelection = document.getElementById("btnClearSelection");
    const progressArea = document.getElementById("inferenceProgressArea");
    const progressStepText = document.getElementById("inferenceProgressStep");

    if (toggleUploadBtn && uploadStageCard) {
      toggleUploadBtn.addEventListener("click", function () {
        uploadStageCard.style.display = "block";
        uploadStageCard.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    if (closeUploadBtn && uploadStageCard) {
      closeUploadBtn.addEventListener("click", function () {
        uploadStageCard.style.display = "none";
      });
    }

    function showError(msg) {
      if (!uploadErrorBox) return;
      uploadErrorBox.textContent = msg;
      uploadErrorBox.style.display = "block";
    }

    function clearError() {
      if (!uploadErrorBox) return;
      uploadErrorBox.textContent = "";
      uploadErrorBox.style.display = "none";
    }

    let selectedFile = null;

    function handleSelectedFile(file) {
      clearError();
      if (!file) return;

      const validTypes = ["image/jpeg", "image/jpg", "image/png"];
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      if (!validTypes.includes(file.type) && !["jpg", "jpeg", "png"].includes(ext)) {
        showError(`Unsupported file format (${ext.toUpperCase() || "Unknown"}). Please select a JPG, JPEG, or PNG chest X-ray image.`);
        fileInput.value = "";
        selectedFile = null;
        if (previewBox) previewBox.style.display = "none";
        return;
      }

      if (file.size === 0) {
        showError("The selected file is empty (0 bytes). Please choose a valid chest X-ray image.");
        return;
      }

      if (file.size > 16 * 1024 * 1024) {
        showError("File size exceeds the 16 MB limit. Please choose a smaller chest X-ray image.");
        return;
      }

      selectedFile = file;
      const reader = new FileReader();
      reader.onload = function (e) {
        if (previewImg) previewImg.src = e.target.result;
        if (previewFilename) previewFilename.textContent = file.name;
        if (previewMeta) {
          const kb = (file.size / 1024).toFixed(1);
          previewMeta.textContent = `Format: ${ext.toUpperCase()} · Size: ${kb} KB · Ready for CLAHE Preprocessing & VLM Inference`;
        }
        if (previewBox) previewBox.style.display = "flex";
      };
      reader.readAsDataURL(file);
    }

    if (dropzone && fileInput) {
      dropzone.addEventListener("click", function () {
        fileInput.click();
      });

      fileInput.addEventListener("change", function () {
        if (fileInput.files && fileInput.files[0]) {
          handleSelectedFile(fileInput.files[0]);
        }
      });

      dropzone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropzone.classList.add("dragover");
      });

      dropzone.addEventListener("dragleave", function () {
        dropzone.classList.remove("dragover");
      });

      dropzone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleSelectedFile(e.dataTransfer.files[0]);
        }
      });
    }

    if (btnClearSelection) {
      btnClearSelection.addEventListener("click", function () {
        selectedFile = null;
        if (fileInput) fileInput.value = "";
        if (previewBox) previewBox.style.display = "none";
        clearError();
      });
    }

    function executeAnalysisRequest(formData) {
      clearError();
      if (progressArea) progressArea.style.display = "block";
      if (btnRunAnalysis) btnRunAnalysis.disabled = true;

      const steps = [
        "Step 1/3: Validating image headers & running CLAHE contrast preprocessing...",
        "Step 2/3: Extracting thoracic zone densities & running ThoraxVLM report generation...",
        "Step 3/3: Saving structured report draft & initializing chatbot in MySQL history...",
      ];
      let stepIdx = 0;
      if (progressStepText) progressStepText.textContent = steps[0];
      const stepTimer = setInterval(function () {
        stepIdx = Math.min(steps.length - 1, stepIdx + 1);
        if (progressStepText) progressStepText.textContent = steps[stepIdx];
      }, 420);

      fetch("/api/analyze", {
        method: "POST",
        body: formData,
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (result) {
          clearInterval(stepTimer);
          if (!result.ok) {
            if (progressArea) progressArea.style.display = "none";
            if (btnRunAnalysis) btnRunAnalysis.disabled = false;
            showError(result.data.error || "Analysis failed. Please try another chest X-ray image.");
            return;
          }
          window.location.href = result.data.redirect_url || "/dashboard";
        })
        .catch(function () {
          clearInterval(stepTimer);
          if (progressArea) progressArea.style.display = "none";
          if (btnRunAnalysis) btnRunAnalysis.disabled = false;
          showError("Network error while communicating with the inference server. Please try again.");
        });
    }

    if (btnRunAnalysis) {
      btnRunAnalysis.addEventListener("click", function () {
        if (!selectedFile) {
          showError("Please select a chest X-ray image file first.");
          return;
        }
        const fd = new FormData();
        fd.append("xray_image", selectedFile);
        executeAnalysisRequest(fd);
      });
    }

    // Built-in Clinical Sample Radiograph buttons
    document.querySelectorAll(".js-sample-xray-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const sampleId = btn.getAttribute("data-sample-id");
        if (!sampleId) return;
        const fd = new FormData();
        fd.append("sample_id", sampleId);
        executeAnalysisRequest(fd);
      });
    });
  }

  // ---------------------------------------------------------------------------
  // FR-07: Contextual Chatbot Controller
  // ---------------------------------------------------------------------------
  function initChatbot() {
    const chatForm = document.getElementById("chatbotForm");
    const chatInput = document.getElementById("chatbotInput");
    const chatSendBtn = document.getElementById("chatbotSendBtn");
    const chatStream = document.getElementById("chatMessagesStream");

    if (!chatForm || !chatInput || !chatStream) return;

    const analysisId = chatForm.getAttribute("data-analysis-id");

    function appendMessageBubble(role, text, timestamp) {
      const row = document.createElement("div");
      row.className = `chat-bubble-row ${role}`;

      const avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.textContent = role === "assistant" ? "AI" : "YOU";

      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";

      const contentDiv = document.createElement("div");
      if (role === "assistant") {
        contentDiv.innerHTML = renderMarkdown(text);
      } else {
        contentDiv.textContent = text;
      }

      const ts = document.createElement("span");
      ts.className = "chat-timestamp";
      ts.textContent = timestamp || "Just now";

      bubble.appendChild(contentDiv);
      bubble.appendChild(ts);
      row.appendChild(avatar);
      row.appendChild(bubble);
      chatStream.appendChild(row);
      chatStream.scrollTop = chatStream.scrollHeight;
      return row;
    }

    function sendQuestion(questionText) {
      const q = (questionText || "").trim();
      if (!q || !analysisId) return;

      chatInput.value = "";
      chatSendBtn.disabled = true;

      appendMessageBubble("user", q, "Sending...");
      const loadingRow = appendMessageBubble("assistant", "Analyzing report context", "Thinking...");
      const loadingContent = loadingRow ? loadingRow.querySelector(".chat-bubble > div") : null;
      if (loadingContent) {
        loadingContent.innerHTML =
          '<span class="typing-dots">Analyzing report context<span class="dot"></span><span class="dot"></span><span class="dot"></span></span>';
      }

      fetch(`/api/analysis/${analysisId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q }),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (resObj) {
          chatSendBtn.disabled = false;
          if (loadingRow && loadingRow.parentNode) {
            loadingRow.parentNode.removeChild(loadingRow);
          }
          if (!resObj.ok) {
            appendMessageBubble(
              "assistant",
              `**Error:** ${resObj.data.error || "Could not generate response."}`,
              "System Notice"
            );
            return;
          }
          const aMsg = resObj.data.assistant_message;
          appendMessageBubble("assistant", aMsg.message_text, aMsg.created_at);
        })
        .catch(function () {
          chatSendBtn.disabled = false;
          if (loadingRow && loadingRow.parentNode) {
            loadingRow.parentNode.removeChild(loadingRow);
          }
          appendMessageBubble(
            "assistant",
            "**Connection Error:** Unable to reach the chatbot service. Please try again.",
            "System Notice"
          );
        });
    }

    chatForm.addEventListener("submit", function (e) {
      e.preventDefault();
      sendQuestion(chatInput.value);
    });

    document.querySelectorAll(".js-quick-prompt").forEach(function (chip) {
      chip.addEventListener("click", function () {
        const promptText = chip.getAttribute("data-prompt");
        if (promptText) {
          sendQuestion(promptText);
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // FR-12: Delete Analysis Confirmation Modal
  // ---------------------------------------------------------------------------
  function initDeleteModal() {
    const modal = document.getElementById("deleteConfirmModal");
    const labelSpan = document.getElementById("deleteModalCaseLabel");
    const btnConfirm = document.getElementById("btnConfirmDelete");
    const btnCancel = document.getElementById("btnCancelDelete");

    if (!modal || !btnConfirm) return;

    let targetAnalysisId = null;

    document.querySelectorAll(".js-delete-analysis-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        targetAnalysisId = btn.getAttribute("data-analysis-id");
        const label = btn.getAttribute("data-case-label") || `Analysis #${targetAnalysisId}`;
        if (labelSpan) labelSpan.textContent = label;
        modal.classList.add("open");
      });
    });

    if (btnCancel) {
      btnCancel.addEventListener("click", function () {
        modal.classList.remove("open");
        targetAnalysisId = null;
      });
    }

    btnConfirm.addEventListener("click", function () {
      if (!targetAnalysisId) return;
      btnConfirm.disabled = true;
      btnConfirm.textContent = "Deleting...";

      fetch(`/api/analysis/${targetAnalysisId}/delete`, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (resObj) {
          if (resObj.ok) {
            window.location.href = "/dashboard";
          } else {
            alert(resObj.data.error || "Could not delete analysis record.");
            btnConfirm.disabled = false;
            btnConfirm.textContent = "Delete Permanently";
            modal.classList.remove("open");
          }
        })
        .catch(function () {
          btnConfirm.disabled = false;
          btnConfirm.textContent = "Delete Permanently";
          modal.classList.remove("open");
        });
    });
  }

  // ---------------------------------------------------------------------------
  // Report Tab Switcher (Structured Clinical View vs Raw Text View)
  // ---------------------------------------------------------------------------
  function initReportTabs() {
    const btnStructured = document.getElementById("btnReportStructured");
    const btnRaw = document.getElementById("btnReportRaw");
    const viewStructured = document.getElementById("reportStructuredView");
    const viewRaw = document.getElementById("reportRawView");
    const btnCopyReport = document.getElementById("btnCopyReport");

    if (btnStructured && btnRaw && viewStructured && viewRaw) {
      btnStructured.addEventListener("click", function () {
        viewStructured.style.display = "block";
        viewRaw.style.display = "none";
        btnStructured.classList.add("active");
        btnRaw.classList.remove("active");
      });
      btnRaw.addEventListener("click", function () {
        viewStructured.style.display = "none";
        viewRaw.style.display = "block";
        btnRaw.classList.add("active");
        btnStructured.classList.remove("active");
      });
    }

    if (btnCopyReport) {
      btnCopyReport.addEventListener("click", function () {
        const rawPre = document.getElementById("rawReportPreText");
        if (!rawPre) return;
        navigator.clipboard.writeText(rawPre.textContent).then(function () {
          const orig = btnCopyReport.textContent;
          btnCopyReport.textContent = "Copied!";
          setTimeout(function () {
            btnCopyReport.textContent = orig;
          }, 1600);
        });
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Cross-app navigation: responsive sidebar and accessible info dialogs
  // ---------------------------------------------------------------------------
  function initAppNavigation() {
    const body = document.body;
    const toggle = document.getElementById("sidebarMobileToggle");
    const sidebar = document.getElementById("appSidebar");
    const scrim = document.getElementById("sidebarScrim");

    function setSidebarOpen(open) {
      body.classList.toggle("sidebar-is-open", open);
      if (toggle) {
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
      }
    }

    if (toggle && sidebar) {
      toggle.addEventListener("click", function () {
        setSidebarOpen(!body.classList.contains("sidebar-is-open"));
      });
      if (scrim) scrim.addEventListener("click", function () { setSidebarOpen(false); });
      sidebar.querySelectorAll("a").forEach(function (link) {
        link.addEventListener("click", function () { setSidebarOpen(false); });
      });
    }

    let lastModalTrigger = null;
    function closeAppModal(modal) {
      if (!modal) return;
      modal.hidden = true;
      if (!document.querySelector("[data-app-modal]:not([hidden])")) {
        body.classList.remove("app-modal-open");
      }
      if (lastModalTrigger && document.contains(lastModalTrigger)) lastModalTrigger.focus();
    }

    document.querySelectorAll("[data-app-modal-open]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        setSidebarOpen(false);
        const modal = document.getElementById(trigger.getAttribute("data-app-modal-open"));
        if (!modal) return;
        lastModalTrigger = trigger;
        modal.hidden = false;
        body.classList.add("app-modal-open");
        const dialog = modal.querySelector('[role="dialog"]');
        if (dialog) window.requestAnimationFrame(function () { dialog.focus(); });
      });
    });

    document.querySelectorAll("[data-app-modal]").forEach(function (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal || event.target.closest("[data-app-modal-close]")) {
          closeAppModal(modal);
        }
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        const openModals = Array.from(document.querySelectorAll("[data-app-modal]:not([hidden])"));
        if (openModals.length) closeAppModal(openModals[openModals.length - 1]);
        setSidebarOpen(false);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAppNavigation();
    formatInitialChatMessages();
    initXrayViewer();
    initUploadWorkflow();
    initChatbot();
    initDeleteModal();
    initReportTabs();
  });
})();
