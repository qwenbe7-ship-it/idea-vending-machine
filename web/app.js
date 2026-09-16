const form = document.querySelector('#idea-form');
const ideaInput = document.querySelector('#idea');
const submitButton = document.querySelector('#submit');
const status = document.querySelector('#status');
const resultSection = document.querySelector('#result');

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

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  status.textContent = '아이디어를 분석하고 있습니다…';
  submitButton.disabled = true;
  resultSection.hidden = true;

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({idea: ideaInput.value}),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || '분석에 실패했습니다.');
    }
    renderResult(payload);
    status.textContent = '분석이 완료되었습니다.';
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '분석에 실패했습니다.';
  } finally {
    submitButton.disabled = false;
  }
});
