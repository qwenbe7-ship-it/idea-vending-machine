/* Additive local validation UX for the existing Bridge workflow.
 *
 * This file deliberately does not duplicate any Bridge business rule. It only
 * observes the existing parse/post flow and renders server-owned validation
 * feedback beside the action that triggered it.
 */

let activeBridgeValidationKind = null;

function bridgeValidationTarget(kind) {
  return document.querySelector(
    kind === 'forge' ? '#forge-validation-status' : '#judge-validation-status',
  );
}

function renderBridgeValidation(kind, state, detail = '') {
  const target = bridgeValidationTarget(kind);
  if (!target) return;
  target.dataset.state = state;
  target.textContent = detail;
  target.hidden = false;
}

function hideBridgeValidation(kind) {
  const target = bridgeValidationTarget(kind);
  if (!target) return;
  target.hidden = true;
  target.textContent = '';
  target.removeAttribute('data-state');
}

function resetBridgeValidation() {
  hideBridgeValidation('forge');
  hideBridgeValidation('judge');
  activeBridgeValidationKind = null;
}

function bridgeValidationErrorDetail(error) {
  const validation = error?.payload?.validation_error;
  if (validation && typeof validation === 'object') {
    const parts = [];
    if (typeof validation.message === 'string' && validation.message.trim()) {
      parts.push(validation.message.trim());
    }
    if (typeof validation.expected_rule === 'string' && validation.expected_rule.trim()) {
      parts.push(`규칙: ${validation.expected_rule.trim()}`);
    }
    if (typeof validation.repair_instruction === 'string' && validation.repair_instruction.trim()) {
      parts.push(`수정 방법: ${validation.repair_instruction.trim()}`);
    }
    if (parts.length) return parts.join(' ');
  }
  if (typeof error?.message === 'string' && error.message.trim()) return error.message.trim();
  return '결과 검증에 실패했습니다. 입력 내용을 확인한 뒤 다시 시도하세요.';
}

function beginBridgeValidation(kind) {
  activeBridgeValidationKind = kind;
  renderBridgeValidation(kind, 'pending', '검증 중…');
}

for (const [selector, kind] of [
  ['#import-forge-result', 'forge'],
  ['#import-judge-result', 'judge'],
]) {
  const button = document.querySelector(selector);
  if (button) {
    button.addEventListener('click', () => beginBridgeValidation(kind), true);
  }
}

const originalParseImportedJson = parseImportedJson;
parseImportedJson = function parseImportedJsonWithLocalValidation(text) {
  try {
    return originalParseImportedJson(text);
  } catch (error) {
    if (activeBridgeValidationKind) {
      renderBridgeValidation(
        activeBridgeValidationKind,
        'error',
        bridgeValidationErrorDetail(error),
      );
    }
    throw error;
  }
};

const originalBridgePostJson = postJson;
postJson = async function postJsonWithBridgeValidation(path, data) {
  if (path === '/api/bridge/forge-request') {
    resetBridgeValidation();
  }

  const kind = path === '/api/bridge/forge-import'
    ? 'forge'
    : (path === '/api/bridge/judge-import' ? 'judge' : null);

  if (kind) beginBridgeValidation(kind);

  try {
    const payload = await originalBridgePostJson(path, data);
    if (kind === 'forge') {
      const count = Number.isInteger(payload?.candidate_count) ? payload.candidate_count : 10;
      renderBridgeValidation('forge', 'success', `검증 완료 · ${count}개 후보`);
      activeBridgeValidationKind = null;
    } else if (kind === 'judge') {
      renderBridgeValidation('judge', 'success', '검증 완료 · 공식 판단 생성');
      activeBridgeValidationKind = null;
    }
    return payload;
  } catch (error) {
    if (kind) {
      renderBridgeValidation(kind, 'error', bridgeValidationErrorDetail(error));
      activeBridgeValidationKind = null;
    }
    throw error;
  }
};
