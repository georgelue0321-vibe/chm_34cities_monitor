const STORAGE_KEY = 'chm_onboarding_done';
const VERSION_KEY = 'chm_onboarding_version';
const ONBOARDING_VERSION = '2';

const STEPS = [
    {
        title: '欢迎使用 CHM 终端',
        subtitle: 'China Housing Monitor',
        content: '本终端用于<strong>辅助研判</strong>中国 34 个核心城市的房地产市场底部信号。通过收储执行、价格走势、资金温度三个维度进行综合评估。',
        highlight: null,
        position: 'center'
    },
    {
        title: '全国底部信号地图',
        subtitle: 'National Signal Map',
        content: '点击左侧标签可展开<strong>全国 34 城底部信号地图</strong>，直观查看各城市信号强度分布。',
        highlight: 'map-trigger-tag',
        position: 'top'
    },
    {
        title: '收储追踪记录',
        subtitle: 'Storage Execution Timeline',
        content: '这是<strong>最核心的参考模块</strong>。国企保障房收储从"政策表态"到"签约收购"推进越深，底部信号越强。每条记录均附有政府官网信源。',
        highlight: 'storage-events-card',
        position: 'top'
    },
    {
        title: '底部信号评分 (BSS)',
        subtitle: 'Bottom Signal Score',
        content: '评分范围 0-100，<strong>分数越高 = 越接近底部</strong>。85+ 为强信号观察，70-85 为政策价格共振，50 以下仍在下跌通道。',
        highlight: 'city-radial-score-card',
        position: 'top'
    },
    {
        title: '全国资金温度',
        subtitle: 'PBOC Re-lending Progress',
        content: '反映央行 3000 亿保障房再贷款的释放进度。数据更新频率取决于央行披露节奏。',
        highlight: 'national-gauge-card',
        position: 'top',
        dynamicNote: true
    },
    {
        title: '更新日志与算法逻辑',
        subtitle: 'Methodology & Changelog',
        content: '点击此处可查看<strong>评分算法权重</strong>、<strong>底部状态跃迁规则</strong>及版本迭代记录。初次使用建议浏览了解评分逻辑。',
        highlight: 'methodology-btn',
        position: 'top'
    },
    {
        title: '切换浅色主题',
        subtitle: 'Theme Toggle',
        content: '点击太阳图标可切换到<strong>浅色主题</strong>，再次点击切回深色。主题设置会自动保存。',
        highlight: 'theme-toggle',
        position: 'top'
    }
];

let currentStep = 0;
let activeSteps = STEPS;
let currentTargetId = null;
let currentStepConfig = null;
let scrollRAF = null;
let onboardingPreviousFocus = null;

function isOnboardingDone() {
    return Number(localStorage.getItem(VERSION_KEY) || 0) >= Number(ONBOARDING_VERSION);
}

function markOnboardingDone() {
    localStorage.setItem(STORAGE_KEY, '1');
    localStorage.setItem(VERSION_KEY, ONBOARDING_VERSION);
}

function onboardingMode() {
    if (Number(localStorage.getItem(VERSION_KEY) || 0) >= Number(ONBOARDING_VERSION)) return 'none';
    return localStorage.getItem(STORAGE_KEY) === '1' ? 'feature' : 'full';
}

function getExtensionOnboardingStep() {
    const host = window.CHMExtensionHost;
    if (!host || typeof host.getOnboardingStep !== 'function') return null;
    const cityId = localStorage.getItem('selected_city') || 'cd';
    const step = host.getOnboardingStep(cityId);
    if (!step || typeof step !== 'object' || !step.title || !step.content) return null;
    return step;
}

function startOnboarding(mode) {
    const selectedMode = mode || onboardingMode();
    if (selectedMode === 'none') return;
    const extensionStep = getExtensionOnboardingStep();
    if (selectedMode === 'feature' && !extensionStep) {
        markOnboardingDone();
        return;
    }
    activeSteps = selectedMode === 'feature' ? [extensionStep] : extensionStep ? [...STEPS, extensionStep] : STEPS;
    onboardingPreviousFocus = document.activeElement;
    currentStep = 0;
    createOverlay();
    renderStep(currentStep);
    document.addEventListener('keydown', handleKeyboard);
}

function createOverlay() {
    const existing = document.getElementById('onboarding-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'onboarding-overlay';
    overlay.innerHTML = `<div id="onboarding-tooltip" class="onboarding-tooltip onboarding-center" role="dialog" aria-modal="true" aria-label="使用指引" tabindex="-1"><div id="onboarding-tooltip-inner"></div></div>`;
    document.body.appendChild(overlay);
}

function renderStep(index) {
    const step = activeSteps[index];
    const tooltip = document.getElementById('onboarding-tooltip');
    const inner = document.getElementById('onboarding-tooltip-inner');

    if (!step || !tooltip || !inner) return;

    currentStepConfig = step;
    currentTargetId = step.highlight;

    let dynamicNote = '';
    if (step.dynamicNote && window.MONITOR_DB && window.MONITOR_DB.pboc_global) {
        const pboc = window.MONITOR_DB.pboc_global;
        if (pboc.pboc_is_stale && pboc.pboc_stale_months > 0) {
            dynamicNote = `<div class="onboarding-stale-note">当前已停更超 ${pboc.pboc_stale_months} 个月，评分已受限</div>`;
        }
    }

    inner.innerHTML = `
        <div class="onboarding-header">
            <span class="onboarding-step-badge">${index + 1}/${activeSteps.length}</span>
            <h3 class="onboarding-title">${step.title}</h3>
            <p class="onboarding-subtitle">${step.subtitle}</p>
        </div>
        <div class="onboarding-body">
            <p>${step.content}</p>
            ${dynamicNote}
        </div>
        <div class="onboarding-footer">
            <button onclick="skipOnboarding()" class="onboarding-skip" aria-label="跳过指引">跳过指引</button>
            <div class="onboarding-nav">
                ${index > 0 ? `<button onclick="prevStep()" class="onboarding-prev" aria-label="上一步"><i class="fas fa-chevron-left"></i></button>` : ''}
                <button onclick="activateCurrentStep()" class="onboarding-next" aria-label="${step.actionLabel || (index === activeSteps.length - 1 ? '开始使用' : '下一步')}">
                    ${step.actionLabel || (index === activeSteps.length - 1 ? '开始使用' : '下一步')} <i class="fas fa-chevron-right"></i>
                </button>
            </div>
        </div>
    `;
    requestAnimationFrame(() => inner.querySelector('.onboarding-next')?.focus());

    document.querySelectorAll('.onboarding-highlighted').forEach(el => el.classList.remove('onboarding-highlighted'));

    if (step.highlight) {
        const target = document.getElementById(step.highlight);
        if (target) {
            const vh = window.innerHeight;
            target.classList.add('onboarding-highlighted');
            positionTooltip(target);
            const tooltipEl = document.getElementById('onboarding-tooltip');
            if (tooltipEl) {
                const tooltipRect = tooltipEl.getBoundingClientRect();
                window.scrollBy({ top: tooltipRect.top - vh / 2 + tooltipRect.height / 2, behavior: 'smooth' });
            }
            setTimeout(() => {
                startScrollListener();
            }, 400);
        } else {
            tooltip.className = 'onboarding-tooltip onboarding-center';
            stopScrollListener();
        }
    } else {
        tooltip.className = 'onboarding-tooltip onboarding-center';
        stopScrollListener();
    }
}

function ensureTooltipVisible() {
    const tooltip = document.getElementById('onboarding-tooltip');
    if (!tooltip) return;

    const tooltipRect = tooltip.getBoundingClientRect();
    const vh = window.innerHeight;

    if (tooltipRect.top < 0 || tooltipRect.bottom > vh) {
        tooltip.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function startScrollListener() {
    stopScrollListener();
    window.addEventListener('scroll', onScroll, { passive: true });
}

function stopScrollListener() {
    window.removeEventListener('scroll', onScroll);
    if (scrollRAF) {
        cancelAnimationFrame(scrollRAF);
        scrollRAF = null;
    }
}

function onScroll() {
    if (scrollRAF) return;
    scrollRAF = requestAnimationFrame(() => {
        scrollRAF = null;
        if (currentTargetId) {
            const target = document.getElementById(currentTargetId);
            if (target) {
                positionTooltip(target);
            }
        }
    });
}

function positionTooltip(targetEl) {
    const tooltip = document.getElementById('onboarding-tooltip');
    if (!tooltip || !targetEl) return;

    const rect = targetEl.getBoundingClientRect();
    const gap = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    tooltip.style.position = 'fixed';
    tooltip.style.zIndex = '202';

    if (vw < 768) {
        tooltip.style.width = 'calc(100vw - 24px)';
        tooltip.style.left = '50%';
    } else {
        tooltip.style.width = '360px';
        const halfWidth = 180;
        const center = rect.left + rect.width / 2;
        const minLeft = halfWidth + 12;
        const maxLeft = vw - halfWidth - 12;
        tooltip.style.left = Math.max(minLeft, Math.min(maxLeft, center)) + 'px';
    }

    const showBelow = rect.top < 200;
    if (showBelow) {
        tooltip.style.top = (rect.bottom + gap) + 'px';
        tooltip.style.transform = 'translateX(-50%)';
    } else {
        tooltip.style.top = (rect.top - gap) + 'px';
        tooltip.style.transform = 'translateX(-50%) translateY(-100%)';
    }

    tooltip.className = 'onboarding-tooltip';
}

function nextStep() {
    if (currentStep < activeSteps.length - 1) {
        currentStep++;
        renderStep(currentStep);
    } else {
        completeOnboarding();
    }
}

function prevStep() {
    if (currentStep > 0) {
        currentStep--;
        renderStep(currentStep);
    }
}

function skipOnboarding() {
    completeOnboarding();
}

function completeOnboarding() {
    markOnboardingDone();
    stopScrollListener();
    document.removeEventListener('keydown', handleKeyboard);
    document.querySelectorAll('.onboarding-highlighted').forEach(el => el.classList.remove('onboarding-highlighted'));

    const overlay = document.getElementById('onboarding-overlay');
    if (overlay) {
        overlay.classList.add('onboarding-exit');
        setTimeout(() => overlay.remove(), 300);
    }
    const previousFocus = onboardingPreviousFocus;
    onboardingPreviousFocus = null;
    if (previousFocus?.focus) previousFocus.focus();
}

function activateCurrentStep() {
    const action = currentStepConfig?.onActivate;
    if (typeof action !== 'function') {
        nextStep();
        return;
    }
    completeOnboarding();
    setTimeout(() => action(), 320);
}

function startOnboardingIfNeeded() {
    const mode = onboardingMode();
    if (mode !== 'none') startOnboarding(mode);
}

function handleKeyboard(e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target?.closest?.('button')) return;
    if (e.key === 'Tab') {
        const focusable = document.querySelectorAll('#onboarding-tooltip button:not([disabled])');
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        return;
    }
    switch (e.key) {
        case 'Enter':
        case ' ':
            e.preventDefault();
            activateCurrentStep();
            break;
        case 'Escape':
            e.preventDefault();
            skipOnboarding();
            break;
        case 'ArrowRight':
            e.preventDefault();
            activateCurrentStep();
            break;
        case 'ArrowLeft':
            e.preventDefault();
            prevStep();
            break;
    }
}

window.startOnboarding = startOnboarding;
window.isOnboardingDone = isOnboardingDone;
window.nextStep = nextStep;
window.prevStep = prevStep;
window.skipOnboarding = skipOnboarding;
window.startOnboardingIfNeeded = startOnboardingIfNeeded;
window.activateCurrentStep = activateCurrentStep;
