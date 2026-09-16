const form = document.querySelector('#idea-form');
const ideaInput = document.querySelector('#idea');
const submitButton = document.querySelector('#evolve-submit');
const status = document.querySelector('#status');
const runtimeSection = document.querySelector('#runtime-progress');
const decisionSection = document.querySelector('#executive-decision');
const candidateSection = document.querySelector('#candidate-section');
const evidenceSection = document.querySelector('#evidence-report');
const detailSection = document.querySelector('#detailed-report');
const packageSection = document.querySelector('#package');
const approveButton = document.querySelector('#approve-direction');

let currentRuntimeId = '';
let currentDocuments = {};

const STAGE_LABELS = {
  capture: '아이디어 구조 파악',
  landscape_research: '글로벌 시장·문제·반대 근거 조사',
  assumption_analysis: '숨은 전제 분석',
  reframing: '관점 재구성',
  mechanism_transfer: '타 산업 메커니즘 이전',
  candidate_forge: '10개 사업 후보 생성',
  collision_research: '경쟁·선행사례 충돌검사',
  independent_evaluation: '10개 후보 독립 현실평가',
  decision: '최종 경영판단',
  report_assembly: '대표이사 보고서 구성',
};

const STATUS_LABELS = {
  completed: '완료',
  incomplete: '증거 부족 / 미완료',
  failed: '내부 검증 실패',
  running: '진행 중',
  pending: '대기',
};

function asText(value, fallback = '—') {
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return fallback;
}

function setText(selector, value) {
  const target = document.querySelector(selector);
  if (target) target.textContent = asText(value);
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = asText(text, '');
  return element;
}

function fillList(selector, values) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  for (const value of Array.isArray(values) ? values : []) {
    list.appendChild(createElement('li', '', value));
  }
}

function appendDefinition(list, term, value) {
  const dt = createElement('dt', '', term);
  const dd = createElement('dd', '', value);
  list.append(dt, dd);
}

async function postJson(path, data) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }
  if (!response.ok) {
    const error = new Error(payload.error || '요청 처리에 실패했습니다.');
    error.payload = payload;
    throw error;
  }
  return payload;
}

function hideOutput() {
  for (const section of [runtimeSection, decisionSection, candidateSection, evidenceSection, detailSection, packageSection]) {
    section.hidden = true;
  }
  currentRuntimeId = '';
  currentDocuments = {};
  approveButton.disabled = true;
}

function renderRuntime(runtime) {
  const events = document.querySelector('#runtime-events');
  const failure = document.querySelector('#runtime-failure');
  events.replaceChildren();
  failure.hidden = true;
  failure.textContent = '';
  runtimeSection.hidden = false;

  const runtimeStatus = runtime && runtime.status ? runtime.status : 'failed';
  setText('#runtime-state', STATUS_LABELS[runtimeStatus] || runtimeStatus);

  for (const event of Array.isArray(runtime?.stage_events) ? runtime.stage_events : []) {
    const item = createElement('li', `timeline-item ${event.status || ''}`);
    const title = createElement('strong', '', STAGE_LABELS[event.stage] || event.stage);
    const meta = createElement('span', 'timeline-meta', `${event.status || ''} · ${event.message_code || ''}`);
    item.append(title, meta);
    events.appendChild(item);
  }

  if (runtime?.failure) {
    failure.textContent = `운영 상태: ${runtime.failure.code} · 단계: ${STAGE_LABELS[runtime.failure.stage] || runtime.failure.stage}`;
    failure.hidden = false;
  }
}

function renderMarketSnapshot(market) {
  const container = document.querySelector('#market-snapshot');
  container.replaceChildren();
  if (!market || typeof market !== 'object') return;

  const summary = [
    ['시장 단계', market.stage],
    ['핵심 구매자', market.buyer],
  ];
  for (const [label, value] of summary) {
    const card = createElement('div', 'market-card');
    card.append(createElement('span', 'market-label', label), createElement('strong', '', value));
    container.appendChild(card);
  }

  const groups = [
    ['현재 시장', market.current_market],
    ['향후 시장', market.forecast_market],
    ['성장 신호', market.growth],
  ];
  for (const [label, entries] of groups) {
    const card = createElement('div', 'market-card');
    card.appendChild(createElement('span', 'market-label', label));
    const list = createElement('ul', 'compact-list');
    for (const entry of Array.isArray(entries) ? entries : []) {
      list.appendChild(createElement('li', '', entry.label));
    }
    card.appendChild(list);
    container.appendChild(card);
  }
}

function renderNextValidation(validation) {
  const list = document.querySelector('#next-validation');
  list.replaceChildren();
  if (!validation || typeof validation !== 'object') return;
  appendDefinition(list, '실행', validation.action);
  appendDefinition(list, '통과 조건', validation.pass_condition);
  appendDefinition(list, '실패 조건', validation.fail_condition);
}

function renderExecutive(result) {
  const state = result.state || {};
  const brief = state.executive_brief || result.report || {};
  decisionSection.hidden = false;
  setText('#decision-value', state.decision);
  setText('#confidence-value', `신뢰도 ${asText(state.confidence)}`);
  setText('#decision-thesis', brief.thesis);
  setText('#why-now', brief.why_now);
  setText('#evolution-delta', brief.evolution_delta);
  setText('#best-customer', brief.best_customer);
  setText('#business-value', brief.business_value);
  fillList('#reasons-for', brief.reasons_for);
  fillList('#reasons-against', brief.reasons_against);
  fillList('#critical-unknowns', brief.critical_unknowns);
  renderMarketSnapshot(brief.market_snapshot);
  renderNextValidation(brief.cheapest_next_validation);

  const guidance = document.querySelector('#approval-guidance');
  const canApprove = result.runtime?.status === 'completed' && ['GO', 'MODIFY'].includes(state.decision);
  approveButton.disabled = !canApprove;
  if (canApprove) {
    guidance.textContent = state.decision === 'MODIFY'
      ? '검증을 통과한 진화 아이디어를 승인하면 개발 패키지를 생성합니다.'
      : '원안이 가장 강한 방향입니다. 승인하면 원안을 기준으로 개발 패키지를 생성합니다.';
  } else if (state.decision === 'HOLD') {
    guidance.textContent = 'HOLD: 결정에 필요한 증거가 부족합니다. 위의 다음 검증을 먼저 수행해야 합니다.';
  } else if (state.decision === 'KILL') {
    guidance.textContent = 'KILL: 원안과 대안 모두에서 증거 기반 치명적 제약이 확인되어 개발 handoff가 차단됩니다.';
  } else {
    guidance.textContent = '완료된 GO 또는 MODIFY 판단만 승인할 수 있습니다.';
  }
}

function renderDimensionSummary(statuses) {
  const summary = createElement('div', 'dimension-summary');
  const counts = {strong: 0, mixed: 0, weak: 0, unknown: 0};
  for (const statusValue of Object.values(statuses || {})) {
    if (Object.hasOwn(counts, statusValue)) counts[statusValue] += 1;
  }
  for (const key of ['strong', 'mixed', 'weak', 'unknown']) {
    summary.appendChild(createElement('span', `dimension-chip ${key}`, `${key} ${counts[key]}`));
  }
  return summary;
}

function renderStringListBlock(title, values) {
  const block = createElement('div', 'detail-block');
  block.appendChild(createElement('h5', '', title));
  const list = createElement('ul', 'compact-list');
  const items = Array.isArray(values) ? values : [];
  if (!items.length) list.appendChild(createElement('li', 'muted', '없음'));
  for (const value of items) list.appendChild(createElement('li', '', value));
  block.appendChild(list);
  return block;
}

function renderValueChain(chain) {
  const block = createElement('div', 'detail-block');
  block.appendChild(createElement('h5', '', '가치 창출 인과사슬'));
  const list = createElement('dl', 'definition-list');
  const labels = {
    current_constraint: '현재 제약',
    intervention: '개입/메커니즘',
    workflow_or_incentive_change: '워크플로/인센티브 변화',
    operational_or_economic_effect: '운영·경제 효과',
    buyer_value: '구매자 가치',
    value_capture: '가치 포착',
  };
  for (const [key, label] of Object.entries(labels)) appendDefinition(list, label, chain?.[key]);
  block.appendChild(list);
  return block;
}

function renderCandidateDetails(candidate, assessment) {
  const wrapper = createElement('div', 'candidate-details');
  const dimensions = createElement('div', 'detail-block');
  dimensions.appendChild(createElement('h5', '', '10개 현실평가 차원'));
  const dimensionList = createElement('dl', 'dimension-list');
  const dimension_statuses = assessment.dimension_statuses || {};
  for (const [dimension, dimensionStatus] of Object.entries(dimension_statuses)) {
    appendDefinition(dimensionList, dimension, dimensionStatus);
  }
  dimensions.appendChild(dimensionList);
  wrapper.appendChild(dimensions);

  wrapper.appendChild(renderStringListBlock('Material Unknowns', assessment.material_unknowns));

  const blockersBlock = createElement('div', 'detail-block');
  blockersBlock.appendChild(createElement('h5', '', 'Hard / Material Blockers'));
  const blockers = assessment.hard_or_material_blockers || [];
  if (!blockers.length) blockersBlock.appendChild(createElement('p', 'muted', '없음'));
  for (const blocker of blockers) {
    blockersBlock.appendChild(createElement('p', '', `${asText(blocker.materiality)} · ${asText(blocker.reason)} · 해결 가능: ${asText(blocker.resolvable)}`));
  }
  wrapper.appendChild(blockersBlock);

  const workflow = createElement('div', 'detail-block two-column-inline');
  const before = createElement('div', 'mini-card');
  before.append(createElement('h5', '', 'Before'), createElement('p', '', candidate.workflow_before));
  const after = createElement('div', 'mini-card');
  after.append(createElement('h5', '', 'After'), createElement('p', '', candidate.workflow_after));
  workflow.append(before, after);
  wrapper.appendChild(workflow);

  wrapper.appendChild(renderValueChain(candidate.value_creation_chain));
  wrapper.appendChild(renderStringListBlock('핵심 의존성', candidate.critical_dependencies));
  wrapper.appendChild(renderStringListBlock('새로운 위험', candidate.new_risks));
  wrapper.appendChild(renderStringListBlock('검증 질문', candidate.validation_questions));
  wrapper.appendChild(renderStringListBlock('Evidence refs', assessment.evidence_claim_ids));
  return wrapper;
}

function renderCandidates(result) {
  const grid = document.querySelector('#candidate-grid');
  grid.replaceChildren();
  const assessments = Array.isArray(result.candidate_reality_assessments)
    ? result.candidate_reality_assessments : [];
  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  const candidatesById = new Map(candidates.map((candidate) => [candidate.candidate_id, candidate]));
  candidateSection.hidden = false;
  setText('#candidate-count', `${assessments.length}개 후보`);

  for (const assessment of assessments) {
    const candidate = candidatesById.get(assessment.candidate_id) || {};
    const card = createElement('article', `candidate-card verdict-${String(assessment.reality_verdict || '').toLowerCase()}`);
    const head = createElement('div', 'candidate-head');
    const titleBox = createElement('div', 'candidate-title-box');
    titleBox.append(
      createElement('span', 'family-label', assessment.family),
      createElement('h3', '', assessment.name),
    );
    head.append(titleBox, createElement('span', 'verdict-badge', assessment.reality_verdict));
    card.append(head, createElement('p', 'candidate-concept', assessment.one_sentence_concept));

    const facts = createElement('dl', 'candidate-facts');
    appendDefinition(facts, 'Primary buyer', candidate.primary_buyer);
    appendDefinition(facts, 'Value capture', candidate.value_capture_model);
    appendDefinition(facts, '강한 근거', assessment.strongest_reason_for);
    appendDefinition(facts, '반대 근거', assessment.strongest_reason_against);
    appendDefinition(facts, '다음 검증', assessment.cheapest_next_validation);
    card.appendChild(facts);
    card.appendChild(renderDimensionSummary(assessment.dimension_statuses));

    const details = createElement('details', 'candidate-expand');
    details.append(createElement('summary', '', '전체 현실평가 보기'), renderCandidateDetails(candidate, assessment));
    card.appendChild(details);
    grid.appendChild(card);
  }
}

function renderEvidence(result) {
  const list = document.querySelector('#evidence-list');
  list.replaceChildren();
  const graph = result.evidence_graph || {};
  const records = Array.isArray(graph.records) ? graph.records : [];
  evidenceSection.hidden = false;

  for (const record of records) {
    const card = createElement('article', 'evidence-card');
    const direction = `${asText(record.supports_or_contradicts)} · Tier ${asText(record.confidence_tier)}`;
    card.append(
      createElement('span', 'family-label', direction),
      createElement('h3', '', record.claim),
      createElement('p', '', `${asText(record.publisher)} · ${asText(record.publication_date)} · ${asText(record.geography)}`),
      createElement('p', 'muted', `claim_id: ${asText(record.claim_id)}`),
    );
    const sourceUrl = record.source_url;
    if (typeof sourceUrl === 'string' && /^https?:\/\//.test(sourceUrl)) {
      const link = createElement('a', 'source-link', record.source_title || '출처 열기');
      link.href = sourceUrl;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      card.appendChild(link);
    }
    list.appendChild(card);
  }
  if (!records.length) list.appendChild(createElement('p', 'muted', '표시할 Evidence Graph record가 없습니다.'));
}

function renderDetailedReport(result) {
  const list = document.querySelector('#detail-list');
  list.replaceChildren();
  const detailed_analysis = result.state?.detailed_analysis || {};
  detailSection.hidden = false;
  for (const [sectionName, section] of Object.entries(detailed_analysis)) {
    const card = createElement('article', 'detail-report-card');
    card.append(
      createElement('span', 'family-label', sectionName.replaceAll('_', ' ')),
      createElement('p', '', section?.summary),
    );
    if (Array.isArray(section?.evidence_refs) && section.evidence_refs.length) {
      card.appendChild(renderStringListBlock('Evidence refs', section.evidence_refs));
    }
    list.appendChild(card);
  }
}

function renderPackage(documents) {
  currentDocuments = documents || {};
  setText('#spec-preview', currentDocuments['spec.md']);
  setText('#design-preview', currentDocuments['design.md']);
  setText('#plan-preview', currentDocuments['plan.md']);
  packageSection.hidden = false;
}

function renderCompletedResult(result) {
  currentRuntimeId = result.runtime?.runtime_id || '';
  renderExecutive(result);
  renderCandidates(result);
  renderEvidence(result);
  renderDetailedReport(result);
}

function renderEvolutionResult(result) {
  renderRuntime(result.runtime || {});
  if (result.runtime?.status !== 'completed') {
    decisionSection.hidden = true;
    candidateSection.hidden = true;
    evidenceSection.hidden = true;
    detailSection.hidden = true;
    approveButton.disabled = true;
    currentRuntimeId = '';
    status.textContent = result.runtime?.status === 'failed'
      ? '내부 계약 검증에 실패했습니다. 사업 판단은 생성하지 않았습니다.'
      : '검증에 필요한 자료가 충분하지 않아 실행을 완료하지 못했습니다. 사업 판단은 생성하지 않았습니다.';
    return;
  }
  renderCompletedResult(result);
  status.textContent = '시장·증거·10개 후보 현실평가와 최종 판단이 완료되었습니다.';
}

function downloadDocument(filename) {
  const content = currentDocuments[filename];
  if (typeof content !== 'string') {
    status.textContent = '먼저 승인된 개발 패키지를 생성해 주세요.';
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
  hideOutput();
  submitButton.disabled = true;
  status.textContent = '아이디어를 조사하고 진화시키고 있습니다. 완료된 서버 검증 결과만 표시합니다…';
  try {
    const payload = await postJson('/api/evolve', {idea: ideaInput.value});
    renderEvolutionResult(payload);
  } catch (error) {
    const code = error?.payload?.error || '';
    if (code === 'provider_not_configured') {
      status.textContent = '서버 AI Provider가 구성되지 않았습니다. API 키나 내부 설정은 브라우저에 노출하지 않습니다.';
    } else {
      status.textContent = error instanceof Error ? error.message : '진화 실행에 실패했습니다.';
    }
  } finally {
    submitButton.disabled = false;
  }
});

approveButton.addEventListener('click', async () => {
  if (!currentRuntimeId) return;
  approveButton.disabled = true;
  status.textContent = '서버에서 승인 상태를 검증하고 개발 패키지를 생성하고 있습니다…';
  try {
    const payload = await postJson('/api/evolve/approve', {runtime_id: currentRuntimeId});
    renderPackage(payload.documents);
    status.textContent = '방향 승인이 완료되었습니다. spec.md · design.md · plan.md가 생성되었습니다.';
    document.querySelector('#approval-guidance').textContent = '승인 완료: 동일 runtime 재승인 시 같은 개발 패키지를 반환합니다.';
  } catch (error) {
    const decision = error?.payload?.decision;
    status.textContent = decision
      ? `${decision} 상태는 개발 handoff가 차단됩니다.`
      : (error instanceof Error ? error.message : '승인 처리에 실패했습니다.');
    approveButton.disabled = false;
  }
});

document.querySelectorAll('[data-download]').forEach((button) => {
  button.addEventListener('click', () => downloadDocument(button.dataset.download));
});
