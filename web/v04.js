(() => {
  const form = document.querySelector('#idea-form');
  const ideaInput = document.querySelector('#idea');
  const submitButton = document.querySelector('#evolve-submit');
  const statusNode = document.querySelector('#status');
  const modeBadge = document.querySelector('.primary-mode');
  const hero = document.querySelector('.hero');

  if (!form || !ideaInput || !submitButton || !statusNode || !hero) return;

  let bridgeFallbackEnabled = false;
  let autonomousConfigured = false;

  submitButton.textContent = '자동 분석 시작';
  submitButton.setAttribute('aria-label', '자동 분석 시작');

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function addAutonomousWorkflow() {
    const workflow = element('div', 'validation-card');
    workflow.id = 'autonomous-workflow';
    workflow.append(
      element('p', 'eyebrow', 'AUTONOMOUS DUE DILIGENCE'),
      element('h3', '', '아이디어 한 번 입력하면 검증 전체를 자동 실행합니다.'),
      element(
        'p',
        'section-copy',
        '시장 자료를 조사하고 반대 근거를 찾은 뒤 10개 대안을 만들고 독립 심사하여 서버가 최종 결정을 계산합니다.'
      ),
    );

    const stages = element('ol', 'bridge-steps');
    for (const label of ['시장 조사', '반증 탐색', '10개 대안', '독립 심사', '최종 결정']) {
      const item = element('li');
      item.appendChild(element('strong', '', label));
      stages.appendChild(item);
    }
    workflow.appendChild(stages);
    form.before(workflow);
  }

  function addAutomationSummary() {
    const section = element('section', 'panel');
    section.id = 'automation-summary';
    section.hidden = true;
    section.setAttribute('aria-labelledby', 'automation-summary-title');

    const heading = element('div', 'section-heading');
    const headingText = element('div');
    headingText.append(
      element('p', 'eyebrow', 'AUTONOMOUS DUE DILIGENCE'),
      element('h2', '', '자동 검증 실행 증거'),
    );
    headingText.querySelector('h2').id = 'automation-summary-title';
    heading.appendChild(headingText);
    section.appendChild(heading);

    const grid = element('div', 'market-grid');
    const metrics = [
      ['근거', 'automation-evidence-count'],
      ['반대 근거', 'automation-counter-evidence-count'],
      ['대안', 'automation-candidate-count'],
      ['독립 심사', 'automation-critique-count'],
      ['결정', 'automation-decision'],
    ];
    for (const [label, id] of metrics) {
      const card = element('article', 'market-card');
      card.append(element('span', 'market-label', label));
      const value = element('strong', '', '—');
      value.id = id;
      card.appendChild(value);
      grid.appendChild(card);
    }
    section.appendChild(grid);

    const bridgeSection = document.querySelector('#bridge-workflow');
    if (bridgeSection) bridgeSection.before(section);
    else hero.after(section);
  }

  function addBridgeFallbackControl() {
    const details = element('details', 'candidate-expand');
    details.id = 'bridge-fallback';
    const summary = element('summary', '', '고급 옵션 · ChatGPT Plus Bridge 사용');
    const copy = element(
      'p',
      'muted',
      '자동 분석 API를 사용할 수 없을 때만 선택하세요. 이 모드는 ChatGPT와 결과를 직접 주고받는 수동 fallback입니다.'
    );
    const enable = element('button', 'secondary-button', 'Bridge fallback 사용');
    enable.id = 'enable-bridge-fallback';
    enable.type = 'button';
    enable.addEventListener('click', () => {
      bridgeFallbackEnabled = true;
      if (typeof resetBridge === 'function') resetBridge();
      submitButton.textContent = 'Bridge로 분석 시작';
      submitButton.setAttribute('aria-label', 'ChatGPT Plus로 분석');
      statusNode.textContent = 'Bridge fallback을 선택했습니다. 아이디어를 확인한 뒤 분석 시작을 누르세요.';
      form.scrollIntoView({behavior: 'smooth', block: 'center'});
    });
    details.append(summary, copy, enable);
    statusNode.after(details);
  }

  function setMetric(id, value) {
    const node = document.querySelector(`#${id}`);
    if (node) node.textContent = String(value ?? '—');
  }

  function renderAutomationSummary(summary) {
    const section = document.querySelector('#automation-summary');
    if (!section) return;
    setMetric('automation-evidence-count', summary.evidence_count);
    setMetric('automation-counter-evidence-count', summary.contradicting_evidence_count);
    setMetric('automation-candidate-count', summary.candidate_count);
    setMetric('automation-critique-count', summary.independent_critique_count);
    setMetric('automation-decision', summary.decision);
    section.hidden = false;
  }

  async function refreshAutonomousReadiness() {
    try {
      const response = await fetch('/readyz', {headers: {'Accept': 'application/json'}});
      if (!response.ok) return;
      const ready = await response.json();
      autonomousConfigured = ready?.modes?.autonomous_due_diligence === 'ready';
      if (modeBadge) {
        modeBadge.textContent = autonomousConfigured
          ? '기본 · 자동 Due Diligence'
          : '자동 엔진 설정 필요 · Bridge fallback 가능';
      }
    } catch (_error) {
      autonomousConfigured = false;
    }
  }

  addAutonomousWorkflow();
  addAutomationSummary();
  addBridgeFallbackControl();
  refreshAutonomousReadiness();

  form.addEventListener('submit', async (event) => {
    if (bridgeFallbackEnabled) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    submitButton.disabled = true;
    if (typeof hideOutput === 'function') hideOutput();
    if (typeof resetBridge === 'function') resetBridge();
    const summarySection = document.querySelector('#automation-summary');
    if (summarySection) summarySection.hidden = true;

    statusNode.textContent = autonomousConfigured
      ? '시장 조사 → 반증 탐색 → 10개 대안 → 독립 심사 → 최종 결정을 자동 실행 중입니다…'
      : '자동 분석 엔진 연결 상태를 확인하고 있습니다…';

    try {
      const result = await postJson('/api/evolve', {idea: ideaInput.value});
      renderAutomationSummary(result.automation_summary || {});
      renderEvolutionResult(result);
    } catch (error) {
      if (error?.payload?.error === 'provider_not_configured') {
        statusNode.textContent = '자동 분석 엔진이 아직 설정되지 않았습니다. 운영자 설정 후 한 번의 클릭으로 전체 검증이 실행됩니다.';
        const fallback = document.querySelector('#bridge-fallback');
        if (fallback) fallback.open = true;
      } else {
        statusNode.textContent = error instanceof Error ? error.message : '자동 분석 실행에 실패했습니다.';
      }
    } finally {
      submitButton.disabled = false;
    }
  }, true);
})();
