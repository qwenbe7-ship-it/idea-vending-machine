const form = document.querySelector('#idea-form');
const ideaInput = document.querySelector('#idea');
const submitButton = document.querySelector('#evolve-submit');
const status = document.querySelector('#status');
const bridgeSection = document.querySelector('#bridge-workflow');
const judgeStep = document.querySelector('#judge-step');
const runtimeSection = document.querySelector('#runtime-progress');
const decisionSection = document.querySelector('#executive-decision');
const candidateSection = document.querySelector('#candidate-section');
const evidenceSection = document.querySelector('#evidence-report');
const detailSection = document.querySelector('#detailed-report');
const packageSection = document.querySelector('#package');
const approveButton = document.querySelector('#approve-direction');

const MAX_BRIDGE_CLIENT_BYTES = 1024 * 1024;

let currentBridgeSessionId = '';
let currentBridgeVersion = '';
let currentForgePackage = null;
let currentJudgePackage = null;
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
  list.append(createElement('dt', '', term), createElement('dd', '', value));
}

async function parseResponse(response) {
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

async function postJson(path, data) {
  return parseResponse(await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data),
  }));
}

async function getJson(path) {
  return parseResponse(await fetch(path, {headers: {'Accept': 'application/json'}}));
}

function hideOutput() {
  for (const section of [runtimeSection, decisionSection, candidateSection, evidenceSection, detailSection, packageSection]) {
    section.hidden = true;
  }
  currentRuntimeId = '';
  currentDocuments = {};
  approveButton.disabled = true;
}

function resetBridge() {
  currentBridgeSessionId = '';
  currentBridgeVersion = '';
  currentForgePackage = null;
  currentJudgePackage = null;
  bridgeSection.hidden = true;
  judgeStep.hidden = true;
  document.querySelector('#forge-result-input').value = '';
  document.querySelector('#judge-result-input').value = '';
  setText('#forge-package', '');
  setText('#judge-package', '');
  setText('#forge-state', '대기');
  setText('#judge-state', '대기');
}

ideaInput.addEventListener('input', () => {
  if (
    currentForgePackage
    && typeof currentForgePackage.raw_idea === 'string'
    && currentForgePackage.raw_idea !== ideaInput.value
  ) {
    resetBridge();
    status.textContent = '아이디어가 변경되었습니다. 이전 Bridge 세션을 닫았습니다. 새 분석을 시작하세요.';
  }
});

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function buildChatGPTPrompt(packageData) {
  if (!packageData || typeof packageData !== 'object') return '';
  return `${asText(packageData.chatgpt_instruction, '')}\n\nPACKAGE JSON:\n${prettyJson(packageData)}`;
}

function legacyClipboardCopy(text) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-10000px';
  textarea.style.top = '0';
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  let copied = false;
  try {
    copied = document.execCommand('copy');
  } catch (_error) {
    copied = false;
  }
  textarea.remove();
  return copied;
}

async function copyTextWithFallback(text, successMessage) {
  if (!text) {
    status.textContent = '복사할 내용이 없습니다.';
    return false;
  }

  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = successMessage;
      return true;
    } catch (_error) {
      // Some browsers deny the async Clipboard API even after a user click.
      // Fall through to the legacy selection-based copy path.
    }
  }

  if (legacyClipboardCopy(text)) {
    status.textContent = successMessage;
    return true;
  }

  status.textContent = '자동 복사가 차단되었습니다. 아래 고급 옵션에서 내용을 직접 선택해 복사해 주세요.';
  return false;
}

async function copyText(text, successMessage) {
  return copyTextWithFallback(text, successMessage);
}

function downloadJson(filename, value) {
  if (!value || typeof value !== 'object') {
    status.textContent = '다운로드할 JSON이 없습니다.';
    return;
  }
  const blob = new Blob([prettyJson(value)], {type: 'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function stripCodeFence(text) {
  const trimmed = String(text || '').trim();
  if (!trimmed.startsWith('```')) return trimmed;
  const firstBreak = trimmed.indexOf('\n');
  const lastFence = trimmed.lastIndexOf('```');
  if (firstBreak < 0 || lastFence <= firstBreak) return trimmed;
  return trimmed.slice(firstBreak + 1, lastFence).trim();
}

function parseImportedJson(text) {
  const normalized = stripCodeFence(text);
  if (!normalized) {
    throw new Error('ChatGPT 결과를 붙여넣어 주세요.');
  }
  let parsed;
  try {
    parsed = JSON.parse(normalized);
  } catch (_error) {
    throw new Error('ChatGPT 결과가 올바른 JSON이 아닙니다. 최종 JSON 전체를 다시 복사해 주세요.');
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON object가 필요합니다.');
  }
  if (
    Object.hasOwn(parsed, 'bridge_session_id')
    && Object.hasOwn(parsed, 'bridge_version')
    && Object.hasOwn(parsed, 'result')
    && parsed.result
    && typeof parsed.result === 'object'
    && !Array.isArray(parsed.result)
  ) {
    return parsed.result;
  }
  return parsed;
}

function makeBridgeEnvelope(result) {
  return {
    bridge_session_id: currentBridgeSessionId,
    bridge_version: currentBridgeVersion,
    result,
  };
}

async function loadJsonFile(file, textarea) {
  if (!file) return;
  const nameLooksJson = file.name.toLowerCase().endsWith('.json');
  const typeLooksJson = file.type === 'application/json' || file.type === '';
  if (!nameLooksJson || !typeLooksJson) {
    throw new Error('JSON 파일만 선택할 수 있습니다.');
  }
  if (file.size <= 0 || file.size > MAX_BRIDGE_CLIENT_BYTES) {
    throw new Error('JSON 파일은 1MiB 이하만 사용할 수 있습니다.');
  }
  textarea.value = await file.text();
}

function renderBridgePackage(kind, packageData) {
  const isForge = kind === 'forge';
  setText(isForge ? '#forge-package' : '#judge-package', prettyJson(packageData));
  setText(isForge ? '#forge-state' : '#judge-state', isForge ? 'ChatGPT 실행 대기' : '독립 검증 대기');
}

async function refreshReadiness() {
  const indicator = document.querySelector('#api-mode-indicator');
  try {
    const ready = await getJson('/readyz');
    if (ready?.modes?.openai_api === 'configured') {
      indicator.textContent = '보조 · OpenAI API 모드 사용 가능';
      indicator.hidden = false;
    } else {
      indicator.hidden = true;
    }
  } catch (_error) {
    indicator.hidden = true;
  }
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
    item.append(
      createElement('strong', '', STAGE_LABELS[event.stage] || event.stage),
      createElement('span', 'timeline-meta', `${event.status || ''} · ${event.message_code || ''}`),
    );
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
  for (const [label, value] of [['시장 단계', market.stage], ['핵심 구매자', market.buyer]]) {
    const card = createElement('div', 'market-card');
    card.append(createElement('span', 'market-label', label), createElement('strong', '', value));
    container.appendChild(card);
  }
  for (const [label, entries] of [
    ['현재 시장', market.current_market],
    ['향후 시장', market.forecast_market],
    ['성장 신호', market.growth],
  ]) {
    const card = createElement('div', 'market-card');
    card.appendChild(createElement('span', 'market-label', label));
    const list = createElement('ul', 'compact-list');
    for (const entry of Array.isArray(entries) ? entries : []) {
      list.appendChild(createElement('li', '', entry?.label || entry));
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
  for (const value of Object.values(statuses || {})) {
    if (Object.hasOwn(counts, value)) counts[value] += 1;
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
  for (const [dimension, dimensionStatus] of Object.entries(assessment.dimension_statuses || {})) {
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
  const assessments = Array.isArray(result.candidate_reality_assessments) ? result.candidate_reality_assessments : [];
  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  const candidatesById = new Map(candidates.map((candidate) => [candidate.candidate_id, candidate]));
  candidateSection.hidden = false;
  setText('#candidate-count', `${assessments.length}개 후보`);

  for (const assessment of assessments) {
    const candidate = candidatesById.get(assessment.candidate_id) || {};
    const card = createElement('article', `candidate-card verdict-${String(assessment.reality_verdict || '').toLowerCase()}`);
    const head = createElement('div', 'candidate-head');
    const titleBox = createElement('div', 'candidate-title-box');
    titleBox.append(createElement('span', 'family-label', assessment.family), createElement('h3', '', assessment.name));
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
  const records = Array.isArray(result.evidence_graph?.records) ? result.evidence_graph.records : [];
  evidenceSection.hidden = false;
  for (const record of records) {
    const card = createElement('article', 'evidence-card');
    card.append(
      createElement('span', 'family-label', `${asText(record.supports_or_contradicts)} · Tier ${asText(record.confidence_tier)}`),
      createElement('h3', '', record.claim),
      createElement('p', '', `${asText(record.publisher)} · ${asText(record.publication_date)} · ${asText(record.geography)}`),
      createElement('p', 'muted', `claim_id: ${asText(record.claim_id)}`),
    );
    if (typeof record.source_url === 'string' && /^https?:\/\//.test(record.source_url)) {
      const link = createElement('a', 'source-link', record.source_title || '출처 열기');
      link.href = record.source_url;
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
  detailSection.hidden = false;
  for (const [sectionName, section] of Object.entries(result.state?.detailed_analysis || {})) {
    const card = createElement('article', 'detail-report-card');
    card.append(createElement('span', 'family-label', sectionName.replaceAll('_', ' ')), createElement('p', '', section?.summary));
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
  resetBridge();
  submitButton.disabled = true;
  status.textContent = '분석 준비를 만들고 있습니다…';
  try {
    const payload = await postJson('/api/bridge/forge-request', {idea: ideaInput.value});
    currentBridgeSessionId = payload.bridge_session_id;
    currentForgePackage = payload.package;
    currentBridgeVersion = payload.package?.bridge_version || '';
    bridgeSection.hidden = false;
    setText('#bridge-session', `세션 ${currentBridgeSessionId}`);
    renderBridgePackage('forge', currentForgePackage);
    status.textContent = '1/2: ChatGPT에서 아이디어 확장을 실행하고 결과를 붙여넣으세요.';
    bridgeSection.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '분석 준비에 실패했습니다.';
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelector('#copy-forge-prompt').addEventListener('click', () => {
  copyText(buildChatGPTPrompt(currentForgePackage), '실행할 내용을 복사했습니다. 새 ChatGPT 대화에 붙여넣고 실행하세요.');
});

document.querySelector('#copy-forge-json').addEventListener('click', () => {
  copyText(prettyJson(currentForgePackage), '패키지 JSON을 복사했습니다.');
});

document.querySelector('#download-forge-json').addEventListener('click', () => {
  downloadJson('ivm-forge-package.json', currentForgePackage);
});

document.querySelector('#copy-judge-prompt').addEventListener('click', () => {
  copyText(buildChatGPTPrompt(currentJudgePackage), '독립 검증 내용을 복사했습니다. 반드시 별도의 새 ChatGPT 대화에 붙여넣으세요.');
});

document.querySelector('#copy-judge-json').addEventListener('click', () => {
  copyText(prettyJson(currentJudgePackage), '독립 검증 패키지 JSON을 복사했습니다.');
});

document.querySelector('#download-judge-json').addEventListener('click', () => {
  downloadJson('ivm-judge-package.json', currentJudgePackage);
});

document.querySelector('#forge-result-file').addEventListener('change', async (event) => {
  try {
    await loadJsonFile(event.target.files?.[0], document.querySelector('#forge-result-input'));
    status.textContent = '결과 JSON 파일을 불러왔습니다. 계속을 누르세요.';
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '파일을 읽지 못했습니다.';
  }
});

document.querySelector('#judge-result-file').addEventListener('change', async (event) => {
  try {
    await loadJsonFile(event.target.files?.[0], document.querySelector('#judge-result-input'));
    status.textContent = '독립 검증 JSON 파일을 불러왔습니다. 계속을 누르세요.';
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '파일을 읽지 못했습니다.';
  }
});

document.querySelector('#import-forge-result').addEventListener('click', async () => {
  const button = document.querySelector('#import-forge-result');
  button.disabled = true;
  status.textContent = '1/2 결과를 검증하고 있습니다…';
  try {
    const result = parseImportedJson(document.querySelector('#forge-result-input').value);
    await postJson('/api/bridge/forge-import', makeBridgeEnvelope(result));
    setText('#forge-state', '완료 · 10개 후보');
    const judge = await postJson('/api/bridge/judge-request', {bridge_session_id: currentBridgeSessionId});
    currentJudgePackage = judge.package;
    currentBridgeVersion = judge.package?.bridge_version || currentBridgeVersion;
    judgeStep.hidden = false;
    renderBridgePackage('judge', currentJudgePackage);
    status.textContent = '1/2 완료. 2/2: 새 ChatGPT 대화에서 독립 검증을 실행하세요.';
    judgeStep.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '결과 검증에 실패했습니다.';
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#import-judge-result').addEventListener('click', async () => {
  const button = document.querySelector('#import-judge-result');
  button.disabled = true;
  status.textContent = '2/2 결과를 검증하고 최종 판단을 만들고 있습니다…';
  try {
    const result = parseImportedJson(document.querySelector('#judge-result-input').value);
    const completed = await postJson('/api/bridge/judge-import', makeBridgeEnvelope(result));
    setText('#judge-state', '완료 · 공식 판단 생성');
    renderEvolutionResult(completed);
    decisionSection.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : '독립 검증 결과 처리에 실패했습니다.';
  } finally {
    button.disabled = false;
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
    const blockedDecision = error?.payload?.decision;
    status.textContent = blockedDecision
      ? `${blockedDecision} 상태는 개발 handoff가 차단됩니다.`
      : (error instanceof Error ? error.message : '승인 처리에 실패했습니다.');
    approveButton.disabled = false;
  }
});

document.querySelectorAll('[data-download]').forEach((button) => {
  button.addEventListener('click', () => downloadDocument(button.dataset.download));
});

refreshReadiness();