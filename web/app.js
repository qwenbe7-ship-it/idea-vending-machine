const form = document.querySelector('#idea-form');
const ideaInput = document.querySelector('#idea');
const submitButton = document.querySelector('#submit');
const status = document.querySelector('#status');
const resultSection = document.querySelector('#result');
const packageSection = document.querySelector('#package');
const packageButton = document.querySelector('#generate-package');

let currentIdea = '';
let currentDocuments = {};

function setText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function fillList(selector, values) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  for (const value of values) {
    const item = document.createElement('li');
    item.textContent = value;
    list.appendChild(item);
  }
}

function renderResult(result) {
  setText('#automation', `자동화 ${result.automation_level}`);
  setText('#feasibility', `구현성 ${result.feasibility_level}`);
  setText('#problem', result.problem);
  setText('#customer', result.customer);
  fillList('#risks', result.risks);
  fillList('#mvp', result.mvp_scope);
  fillList('#criteria', result.acceptance_criteria);
  resultSection.hidden = false;
}

function renderPackage(documents) {
  setText('#spec-preview', documents['spec.md']);
  setText('#design-preview', documents['design.md']);
  setText('#plan-preview', documents['plan.md']);
  currentDocuments = documents;
  packageSection.hidden = false;
}

async function postIdea(path, idea) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({idea}),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || '요청 처리에 실패했습니다.');
  }
  return payload;
}

function downloadDocument(filename) {
  const content = currentDocuments[filename];
  if (typeof content !== 'string') {
    status.textContent = '먼저 개발 패키지를 생성해 주세요.';
    return;
  }
  const blob = new Blob([content], {type: 'text/markdown;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  status.textContent = '아이디어를 분석하고 있습니다…';
  submitButton.disabled = true;
  resultSection.hidden = true;
  packageSection.hidden = true;
  currentDocuments = {};

  try {
    currentIdea = ideaInput.value;
    const payload = await postIdea('/api/analyze', currentIdea);
    renderResult(payload);
    status.textContent = '분석이 완료되었습니다. 개발 패키지를 생성할 수 있습니다.';
  } catch (error) {
    currentIdea = '';
    status.textContent = error instanceof Error ? error.message : '분석에 실패했습니다.';
  } finally {
    submitButton.disabled = false;
  }
});

packageButton.addEventListener('click', async () => {
  if (!currentIdea) {
    status.textContent = '먼저 아이디어를 분석해 주세요.';
    return;
  }
  status.textContent = '개발 패키지를 생성하고 있습니다…';
  packageButton.disabled = true;
  packageSection.hidden = true;

  try {
    const payload = await postIdea('/api/package', currentIdea);
    renderPackage(payload.documents);
    status.textContent = 'spec.md · design.md · plan.md 생성이 완료되었습니다.';
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '개발 패키지 생성에 실패했습니다.';
  } finally {
    packageButton.disabled = false;
  }
});

document.querySelectorAll('[data-download]').forEach((button) => {
  button.addEventListener('click', () => downloadDocument(button.dataset.download));
});
