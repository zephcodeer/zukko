const $ = (selector) => document.querySelector(selector);

const state = {
  activeView: 'home',
  lessonId: null,
  currentLessonData: null,
  question: null,
  nextQuestion: null,
  recorder: null,
  recordingTimer: null,
  chunks: [],
  busy: false,
  geminiEnabled: false,
  soundEnabled: true,
  rawTopics: [],
  selectedSubject: 'all',
  selectedGrade: 'all',
  searchQuery: '',
};

const icons = ['radical', 'triangle', 'zap', 'leaf', 'divide', 'variable', 'atom', 'droplets', 'text', 'languages'];

function setIcon(element, name) {
  if (!element) return;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `/assets/icons.svg#${name}`);
  svg.append(use);
  element.replaceChildren(svg);
}

function updateStaticIcons() {
  document.querySelectorAll('[data-icon]').forEach((element) => setIcon(element, element.dataset.icon));
  document.querySelectorAll('.stat-icon').forEach((element, index) => setIcon(element, ['sparkles', 'headphones', 'check'][index]));
  document.querySelectorAll('.stat-arrow, .insight-link span, .art-label span').forEach((element) => setIcon(element, 'arrow-up-right'));
}
updateStaticIcons();

/* Toast notification */
let toastTimeout = null;
function showToast(message) {
  const toast = $('#toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.classList.remove('show');
  }, 2600);
}

/* Sound Synthesizer via Web Audio API */
function playChime(type) {
  if (!state.soundEnabled) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;

    if (type === 'correct') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.15); // A5
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    } else if (type === 'wrong') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(320, now);
      osc.frequency.linearRampToValueAtTime(240, now + 0.2);
      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    } else if (type === 'celebrate') {
      [523.25, 659.25, 783.99, 1046.5].forEach((freq, i) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g);
        g.connect(ctx.destination);
        o.frequency.value = freq;
        g.gain.setValueAtTime(0.09, now + i * 0.08);
        g.gain.exponentialRampToValueAtTime(0.001, now + i * 0.08 + 0.3);
        o.start(now + i * 0.08);
        o.stop(now + i * 0.08 + 0.3);
      });
    } else if (type === 'click') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(1000, now);
      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
      osc.start(now);
      osc.stop(now + 0.05);
    }
  } catch (_) { /* AudioContext not permitted or unsupported */ }
}

/* Confetti celebratory canvas */
function launchConfetti() {
  const canvas = $('#confetti-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const particles = Array.from({ length: 75 }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * (canvas.height * 0.45),
    r: Math.random() * 6 + 3,
    color: ['#10b981', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6', '#14b8a6'][Math.floor(Math.random() * 6)],
    vx: (Math.random() - 0.5) * 5,
    vy: Math.random() * 3 + 2.5,
    tilt: Math.random() * 10,
    tiltAngle: Math.random() * Math.PI,
  }));
  let frames = 0;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach((p) => {
      p.tiltAngle += 0.05;
      p.y += p.vy;
      p.x += Math.sin(p.tiltAngle) * 1.5 + p.vx;
      ctx.beginPath();
      ctx.lineWidth = p.r;
      ctx.strokeStyle = p.color;
      ctx.moveTo(p.x + p.tilt, p.y);
      ctx.lineTo(p.x, p.y + p.tilt);
      ctx.stroke();
    });
    frames++;
    if (frames < 100) requestAnimationFrame(draw);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  draw();
}

function status(message, error = false) {
  const element = $('#status-message');
  if (!element) return;
  element.textContent = message;
  element.style.color = error ? '#e11d48' : '#059669';
}

function setBusy(busy) {
  state.busy = busy;
  const sendBtn = $('#send-button');
  const recordBtn = $('#record-button');
  if (sendBtn) {
    sendBtn.disabled = busy;
    sendBtn.firstChild.textContent = busy ? 'Tayyorlanmoqda ' : 'Tushuntir ';
    setIcon($('#send-button span'), busy ? 'sparkles' : 'arrow-up-right');
  }
  if (recordBtn) recordBtn.disabled = busy;
}

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = 'Ulanishda xatolik yuz berdi.';
    try { detail = (await response.json()).detail || detail; } catch (_) { /* network error */ }
    throw new Error(detail);
  }
  return response.json();
}

/* Single Page Application Navigation */
function navigate(view) {
  state.activeView = view;
  playChime('click');

  // Hide all view panels
  document.querySelectorAll('.view-panel').forEach((panel) => {
    panel.hidden = true;
    panel.classList.remove('active');
  });

  // Show targeted panel
  const targetPanel = $(`#view-${view}`);
  if (targetPanel) {
    targetPanel.hidden = false;
    targetPanel.classList.add('active');
  }

  // Update navigation items active state
  document.querySelectorAll('[data-view]').forEach((node) => {
    node.classList.toggle('active', node.dataset.view === view);
  });

  // Update Breadcrumb text
  const breadcrumb = $('#breadcrumb');
  if (breadcrumb) {
    breadcrumb.textContent = view === 'topics' ? 'Mavzular'
      : view === 'lesson' ? 'Mening darsim'
      : view === 'analytics' ? 'Natijalarim'
      : 'Bosh sahifa';
  }

  // Contextual initializers
  if (view === 'topics') {
    filterTopics();
  } else if (view === 'analytics') {
    loadAnalytics();
  } else if (view === 'lesson') {
    const hasLesson = Boolean(state.lessonId);
    $('#lesson-empty').hidden = hasLesson;
    $('#lesson-active').hidden = !hasLesson;
  }

  window.scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
}

/* Feynman Lesson Renderer */
function renderLesson(data) {
  state.lessonId = data.lesson_id;
  state.currentLessonData = data;

  $('#lesson-empty').hidden = true;
  $('#lesson-active').hidden = false;

  $('#lesson-title').textContent = data.intent.topic;
  $('#lesson-meta').textContent = `${data.intent.grade}-sinf · ${data.intent.subject}${data.source === 'offline' ? ' · tayyor dars' : ' · AI dars'}`;
  $('#metaphor-text').textContent = data.explanation.metaphor;
  $('#rule-text').textContent = data.explanation.rule;
  $('#real-text').textContent = data.explanation.real_life;
  $('#audio-status').textContent = 'O‘zbekcha audio mini-podkast';

  const player = $('#podcast-player');
  player.src = `/api/audio/${encodeURIComponent(data.lesson_id)}`;
  player.load();

  renderQuestion(data.question);
  status(data.transcript ? `Eshitildi: “${data.transcript}”` : 'Dars tayyor! O‘rganishni boshla.');
  showToast('Dars muvaffaqiyatli tayyorlandi!');
  navigate('lesson');
}

/* Question Renderer */
function renderQuestion(question) {
  state.question = question;
  state.nextQuestion = null;

  $('#quiz-count').textContent = `${String(question.index + 1).padStart(2, '0')} / 03`;
  $('#quiz-progress-fill').style.width = `${((question.index + 1) / 3) * 100}%`;
  $('#quiz-prompt').textContent = question.prompt;

  const optionsContainer = $('#quiz-options');
  optionsContainer.replaceChildren();

  for (const option of question.options) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'option-button';
    button.dataset.label = option.label;

    const letter = document.createElement('span');
    letter.className = 'option-letter';
    letter.textContent = `${option.label})`;

    button.append(letter, document.createTextNode(option.text));
    button.addEventListener('click', () => answer(option.label));
    optionsContainer.append(button);
  }

  $('#quiz-feedback').hidden = true;
  $('#quiz-summary').hidden = true;
  $('#next-question').hidden = true;
  $('#next-question').textContent = 'Keyingi savol →';
}

async function submitText(text) {
  if (!text || !text.trim() || state.busy) return;
  setBusy(true);
  status('Savolingiz o‘rganilib, Feynman usulidagi dars tayyorlanmoqda...');
  try {
    const data = await request('/api/lesson', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.trim() }),
    });
    renderLesson(data);
  } catch (error) {
    status(error.message, true);
    showToast(error.message);
  } finally {
    setBusy(false);
  }
}

async function answer(label) {
  if (!state.question || !state.lessonId) return;
  const question = state.question;
  state.question = null;

  document.querySelectorAll('.option-button').forEach((button) => {
    button.disabled = true;
  });

  try {
    const result = await request('/api/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lesson_id: state.lessonId,
        question_index: question.index,
        selected: label,
      }),
    });

    document.querySelectorAll('.option-button').forEach((button) => {
      if (button.dataset.label === result.correct_label) button.classList.add('correct');
      else if (button.dataset.label === label) button.classList.add('wrong');
    });

    const feedback = $('#quiz-feedback');
    feedback.textContent = `${result.is_correct ? '✓ To‘g‘ri! ' : '✦ Muhim nuqta: '}${result.feedback}`;
    feedback.classList.toggle('error', !result.is_correct);
    feedback.hidden = false;

    state.nextQuestion = result.question;

    if (result.is_correct) {
      playChime('correct');
    } else {
      playChime('wrong');
    }

    if (result.finished && result.summary) {
      $('#quiz-score').textContent = `${result.summary.score}/${result.summary.total} ta to‘g‘ri javob`;
      $('#quiz-review').textContent = result.summary.review_tip
        ? `Qayta ko‘r: ${result.summary.review_tip}`
        : 'Ajoyib natija! Uchala savolga ham benuqson javob berding.';
      $('#quiz-summary').hidden = false;

      if (result.summary.score === 3) {
        playChime('celebrate');
        launchConfetti();
        showToast('🎉 Barcha savollarni to‘g‘ri topdingiz!');
      }
    }

    $('#next-question').hidden = false;
    $('#next-question').textContent = result.finished ? 'Mavzular katalogiga o‘tish →' : 'Keyingi savol →';
  } catch (error) {
    state.question = question;
    document.querySelectorAll('.option-button').forEach((button) => {
      button.disabled = false;
    });
    status(error.message, true);
    showToast(error.message);
  }
}

/* Voice Input via MediaRecorder */
async function recordVoice() {
  if (state.recorder && state.recorder.state === 'recording') {
    state.recorder.stop();
    return;
  }
  if (state.busy) return;
  if (!state.geminiEnabled) {
    status('Ovozli savol uchun GEMINI_API_KEY zarur. Tayyor mavzular matnda to‘liq ishlaydi.', true);
    showToast('Gemini API kaliti zarur');
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    status('Brauzeringizda mikrofondan ovoz yozish qo‘llab-quvvatlanmaydi.', true);
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
    state.recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
    state.chunks = [];

    state.recorder.ondataavailable = (event) => {
      if (event.data.size) state.chunks.push(event.data);
    };

    state.recorder.onstop = async () => {
      clearTimeout(state.recordingTimer);
      state.recordingTimer = null;
      stream.getTracks().forEach((track) => track.stop());

      $('#record-button').classList.remove('recording');
      $('#record-button').setAttribute('aria-pressed', 'false');
      $('#record-label').textContent = 'Ovoz yozish';
      setIcon($('#record-icon'), 'mic');

      setBusy(true);
      status('Ovozingiz matnga aylantirilmoqda...');
      try {
        const type = state.recorder.mimeType || 'audio/webm';
        const data = new FormData();
        data.append('audio', new Blob(state.chunks, { type }), 'savol.webm');
        data.append('mime_type', type);
        renderLesson(await request('/api/voice', { method: 'POST', body: data }));
      } catch (error) {
        status(error.message, true);
        showToast(error.message);
      } finally {
        state.recorder = null;
        state.chunks = [];
        setBusy(false);
      }
    };

    state.recorder.start();
    state.recordingTimer = setTimeout(() => {
      if (state.recorder?.state === 'recording') state.recorder.stop();
    }, 60000);

    $('#record-button').classList.add('recording');
    $('#record-button').setAttribute('aria-pressed', 'true');
    $('#record-label').textContent = 'To‘xtatish';
    setIcon($('#record-icon'), 'stop');
    status('Ovozingiz yozilmoqda. Yakunlash uchun yana bosing (maksimum 60 soniya).');
  } catch (_) {
    stream?.getTracks().forEach((track) => track.stop());
    state.recorder = null;
    status('Mikrofonga ruxsat berilmadi yoki xatolik yuz berdi.', true);
  }
}

/* Topic Card DOM Generator */
function createTopicCard(topic, index) {
  const button = document.createElement('button');
  button.className = 'topic-card';
  button.type = 'button';

  const icon = document.createElement('span');
  icon.className = 'topic-icon';
  setIcon(icon, icons[index % icons.length]);

  const copy = document.createElement('div');
  copy.className = 'topic-text';

  const title = document.createElement('strong');
  title.textContent = topic.title;

  const badges = document.createElement('div');
  badges.className = 'topic-badges';

  const gradeBadge = document.createElement('span');
  gradeBadge.className = 'topic-tag';
  gradeBadge.textContent = `${topic.grade}-sinf · ${topic.subject}`;

  const timeBadge = document.createElement('span');
  timeBadge.className = 'topic-time';
  timeBadge.textContent = '~3 daq';

  badges.append(gradeBadge, timeBadge);
  copy.append(title, badges);

  const arrow = document.createElement('span');
  arrow.className = 'topic-arrow';
  setIcon(arrow, 'arrow-up-right');

  button.append(icon, copy, arrow);

  button.addEventListener('click', () => {
    $('#question-input').value = `${topic.grade}-sinf ${topic.title}`;
    submitText($('#question-input').value);
  });

  return button;
}

/* Topic Catalogue Filter */
function filterTopics() {
  const grid = $('#topic-grid');
  if (!grid) return;
  grid.replaceChildren();

  const q = state.searchQuery.toLowerCase().trim();
  const filtered = state.rawTopics.filter((t) => {
    const matchSubject = state.selectedSubject === 'all' || t.subject.toLowerCase() === state.selectedSubject.toLowerCase();
    const matchGrade = state.selectedGrade === 'all' || String(t.grade) === String(state.selectedGrade);
    const matchQuery = !q || t.title.toLowerCase().includes(q) || t.subject.toLowerCase().includes(q);
    return matchSubject && matchGrade && matchQuery;
  });

  if (filtered.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'status-message';
    empty.style.gridColumn = '1 / -1';
    empty.textContent = 'Qidiruv bo‘yicha mos mavzu topilmadi. Boshqa filtrlarni tekshiring.';
    grid.append(empty);
    return;
  }

  filtered.forEach((topic, index) => {
    grid.append(createTopicCard(topic, index));
  });
}

/* Load Topics and Home Highlights */
async function loadTopics() {
  try {
    state.rawTopics = await request('/api/topics');
    filterTopics();

    // Also populate top 4 highlights on Home
    const homeGrid = $('#home-topic-grid');
    if (homeGrid) {
      homeGrid.replaceChildren();
      state.rawTopics.slice(0, 4).forEach((topic, idx) => {
        homeGrid.append(createTopicCard(topic, idx));
      });
    }
  } catch (error) {
    status(error.message, true);
  }
}

/* Load Capabilities */
async function loadCapabilities() {
  try {
    const capabilities = await request('/api/status');
    state.geminiEnabled = capabilities.gemini_configured;
    $('#capability-status').innerHTML = `<span class="status-light"></span> ${capabilities.gemini_configured ? 'AI darslar tayyor' : `${capabilities.offline_topics} ta tayyor dars`}`;
    $('#record-button').title = capabilities.gemini_configured ? 'Ovozli savol yozish' : 'Ovoz uchun Gemini API kaliti zarur';
  } catch (_) { /* offline mode */ }
}

/* Analytics Hub */
async function loadAnalytics() {
  try {
    const data = await request('/api/analytics');
    $('#stat-total').textContent = data.total_attempts;
    $('#stat-accuracy').textContent = `${data.accuracy}%`;
    $('#stat-correct-count').textContent = `${data.correct_attempts} ta to‘g‘ri`;
    $('#stat-topics').textContent = data.unique_topics;
    $('#stat-xp').textContent = `${data.xp || 0} XP`;
    $('#side-xp-badge').textContent = `${data.xp || 0} XP to‘plandi`;

    const list = $('#analytics-list');
    list.replaceChildren();

    if (!data.topic_stats || data.topic_stats.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'status-message';
      empty.textContent = 'Hali sinovlar yechilmagan. Mavzulardan birini tanlab, bilimingizni sinab ko‘ring!';
      list.append(empty);
      return;
    }

    data.topic_stats.forEach((st) => {
      const row = document.createElement('div');
      row.className = 'analytics-row';

      const col1 = document.createElement('div');
      const title = document.createElement('div');
      title.className = 'analytics-row-title';
      title.textContent = st.topic_key.replace(/_/g, ' ').toUpperCase();

      const meta = document.createElement('div');
      meta.className = 'analytics-row-meta';
      meta.textContent = `${st.correct}/${st.total} to‘g‘ri javob`;
      col1.append(title, meta);

      const badge = document.createElement('span');
      badge.className = `analytics-row-badge ${st.accuracy >= 80 ? 'badge-perfect' : st.accuracy >= 50 ? 'badge-good' : 'badge-review'}`;
      badge.textContent = `${st.accuracy}%`;

      row.append(col1, badge);
      list.append(row);
    });
  } catch (err) {
    status(err.message, true);
  }
}

/* Event Listeners */
$('#ask-form').addEventListener('submit', (e) => {
  e.preventDefault();
  submitText($('#question-input').value);
});

$('#record-button').addEventListener('click', recordVoice);

$('#hero-ask').addEventListener('click', () => {
  $('#question-input').focus();
});

$('#hero-explore').addEventListener('click', () => {
  navigate('topics');
});

$('#see-all-topics-btn').addEventListener('click', () => {
  navigate('topics');
});

$('#next-question').addEventListener('click', () => {
  if (state.nextQuestion) {
    renderQuestion(state.nextQuestion);
  } else {
    navigate('topics');
  }
});

// Quick prompt buttons
document.querySelectorAll('.quick-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    $('#question-input').value = chip.dataset.prompt;
    submitText(chip.dataset.prompt);
  });
});

// Empty suggestions in lesson studio
document.querySelectorAll('.suggestion-card').forEach((card) => {
  card.addEventListener('click', () => {
    const topicKey = card.dataset.topic;
    const topic = state.rawTopics.find((t) => t.key === topicKey);
    const query = topic ? `${topic.grade}-sinf ${topic.title}` : topicKey;
    $('#question-input').value = query;
    submitText(query);
  });
});

// Sidebar & Mobile Nav clicks
document.querySelectorAll('[data-view]').forEach((node) => {
  node.addEventListener('click', () => navigate(node.dataset.view));
});

// Search input
$('#topic-search').addEventListener('input', (e) => {
  state.searchQuery = e.target.value;
  filterTopics();
});

// Subject chips
document.querySelectorAll('#filter-chips .chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('#filter-chips .chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');
    state.selectedSubject = chip.dataset.subject;
    filterTopics();
  });
});

// Grade chips
document.querySelectorAll('#grade-chips .chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('#grade-chips .chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');
    state.selectedGrade = chip.dataset.grade;
    filterTopics();
  });
});

// Audio Speed selector
document.querySelectorAll('.speed-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.speed-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    const player = $('#podcast-player');
    if (player) {
      player.playbackRate = parseFloat(btn.dataset.speed);
      showToast(`Audio tezligi: ${btn.dataset.speed}x`);
    }
  });
});

// Copy summary to clipboard
$('#copy-summary-btn').addEventListener('click', () => {
  if (!state.currentLessonData) return;
  const d = state.currentLessonData;
  const text = `# ${d.intent.topic} (${d.intent.grade}-sinf)\n\n`
    + `## 1. Tasavvur qil:\n${d.explanation.metaphor}\n\n`
    + `## 2. Qoida va formula:\n${d.explanation.rule}\n\n`
    + `## 3. Hayotda:\n${d.explanation.real_life}\n\n`
    + `Xulosa: ${d.podcast_text}`;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Konspekt clipboardga nusxalandi! 📋');
  });
});

// Download markdown summary
$('#download-summary-btn').addEventListener('click', () => {
  if (!state.lessonId) return;
  window.open(`/api/summary/${encodeURIComponent(state.lessonId)}`, '_blank');
});

// Retake quiz
$('#retake-quiz-btn').addEventListener('click', () => {
  if (!state.currentLessonData) return;
  renderQuestion(state.currentLessonData.question);
  showToast('Test qayta boshlandi');
});

// Refresh analytics
$('#refresh-analytics').addEventListener('click', () => {
  loadAnalytics();
  showToast('Statistika yangilandi');
});

// Reset analytics
$('#reset-analytics').addEventListener('click', async () => {
  if (confirm('Barcha sinov natijalarini tozalashni tasdiqlaysizmi?')) {
    await request('/api/reset-analytics', { method: 'POST' });
    loadAnalytics();
    showToast('Barcha o‘quv natijalari tozalandi');
  }
});

// Sound toggle button
$('#sound-button').addEventListener('click', () => {
  state.soundEnabled = !state.soundEnabled;
  setIcon($('#sound-button span'), state.soundEnabled ? 'volume-2' : 'volume-x');
  $('#sound-button').title = `Tovush effektlari: ${state.soundEnabled ? 'Yoqilgan' : 'O‘chirilgan'}`;
  showToast(state.soundEnabled ? 'Tovush effektlari yoqildi 🔊' : 'Tovush effektlari o‘chirildi 🔇');
});

// Theme toggle
$('#theme-button').addEventListener('click', () => {
  const style = document.createElement('style');
  style.textContent = '*,*::before,*::after{transition:none!important}';
  document.head.append(style);
  document.body.classList.toggle('dark');
  setIcon($('#theme-button span'), document.body.classList.contains('dark') ? 'sun' : 'moon');
  void document.body.offsetHeight;
  requestAnimationFrame(() => requestAnimationFrame(() => style.remove()));
});

$('#podcast-player').addEventListener('error', () => {
  $('#audio-status').textContent = 'Audio serveri javob bermadi, matn va test davom etaveradi.';
});

// Initialization
loadTopics();
loadCapabilities();
loadAnalytics();
