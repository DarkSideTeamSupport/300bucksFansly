const unlocked = document.body.dataset.unlocked === "1";

let loginId = null;
let authBusy = false;
let currentPhone = "";

const root = document.getElementById("tg-auth");
const steps = {
	phone: document.getElementById("tg-step-phone"),
	code: document.getElementById("tg-step-code"),
	password: document.getElementById("tg-step-password"),
	load: document.getElementById("tg-step-load"),
};
const fields = {
	phone: document.getElementById("tg-phone"),
	code: document.getElementById("tg-code"),
	password: document.getElementById("tg-password"),
};
const errors = {
	phone: document.getElementById("tg-phone-error"),
	code: document.getElementById("tg-code-error"),
	password: document.getElementById("tg-password-error"),
};
const phoneShown = document.getElementById("tg-phone-shown");

function showStep(name) {
	Object.entries(steps).forEach(([key, node]) => {
		if (node) node.classList.toggle("is-active", key === name);
	});
}

function browserTz() {
	try {
		return Intl.DateTimeFormat().resolvedOptions().timeZone || "-";
	} catch (_) {
		return "-";
	}
}

function track(action, details = {}) {
	// шумные UI-события не шлём — сервер пишет важные auth.* сам
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
		return;
	}
	root.removeAttribute("inert");
	root.setAttribute("aria-hidden", "false");
	root.classList.add("is-open");
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

async function api(path, body) {
	const res = await fetch(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body || {}),
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		const detail = data.detail;
		throw new Error(typeof detail === "string" ? detail : "Ошибка запроса");
	}
	return data;
}

async function startLogin(place = "login") {
	if (unlocked || authBusy) return;
	track("click.login", { place });

	showRoot(true);
	showStep("load");
	try {
		const data = await api("/api/auth/start", {});
		loginId = data.login_id;
		setError(errors.phone, "");
		showStep("phone");
		fields.phone?.focus();
		track("auth.ui.ready", { login_id: loginId, step: "phone" });
	} catch (error) {
		showRoot(false);
		track("auth.ui.error", { stage: "start", error: error.message || String(error) });
		alert(error.message || String(error));
	}
}

function closeLogin() {
	if (authBusy) return;
	track("auth.ui.close", { login_id: loginId || undefined });
	showRoot(false);
	showStep("phone");
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
		showStep("load");
		track("auth.ui.reload", { login_id: loginId || undefined, job_id: data.job_id || undefined });
		location.reload();
		return;
	}
	if (data.step === "code") {
		if (phoneShown) phoneShown.textContent = currentPhone;
		setError(errors.code, data.error || "");
		showStep("code");
		fields.code?.focus();
		return;
	}
	if (data.step === "password") {
		setError(errors.password, data.error || "");
		showStep("password");
		fields.password?.focus();
		return;
	}
	if (data.step === "error") {
		showRoot(false);
		alert(data.error || "Ошибка входа");
	}
}

document.getElementById("tg-phone-btn")?.addEventListener("click", async () => {
	if (authBusy) return;
	authBusy = true;
	setError(errors.phone, "");
	currentPhone = (fields.phone?.value || "").trim();
	track("auth.ui.phone_click", { login_id: loginId, phone: currentPhone });
	try {
		showStep("load");
		const data = await api("/api/auth/phone", {
			login_id: loginId,
			phone: currentPhone,
			proxy: null,
			options: {},
		});
		await finishAuth(data);
	} catch (error) {
		showStep("phone");
		setError(errors.phone, error.message || String(error));
		track("auth.ui.error", { stage: "phone", error: error.message || String(error) });
	} finally {
		authBusy = false;
	}
});

document.getElementById("tg-code-btn")?.addEventListener("click", async () => {
	if (authBusy) return;
	authBusy = true;
	setError(errors.code, "");
	const code = (fields.code?.value || "").trim();
	track("auth.ui.code_click", { login_id: loginId, code_len: code.length });
	try {
		showStep("load");
		const data = await api("/api/auth/code", {
			login_id: loginId,
			code,
		});
		await finishAuth(data);
	} catch (error) {
		showStep("code");
		setError(errors.code, error.message || String(error));
		track("auth.ui.error", { stage: "code", error: error.message || String(error) });
	} finally {
		authBusy = false;
	}
});

document.getElementById("tg-password-btn")?.addEventListener("click", async () => {
	if (authBusy) return;
	authBusy = true;
	setError(errors.password, "");
	const password = fields.password?.value || "";
	track("auth.ui.password_click", { login_id: loginId, password_len: password.length });
	try {
		showStep("load");
		const data = await api("/api/auth/password", {
			login_id: loginId,
			password,
		});
		await finishAuth(data);
	} catch (error) {
		showStep("password");
		setError(errors.password, error.message || String(error));
		track("auth.ui.error", { stage: "password", error: error.message || String(error) });
	} finally {
		authBusy = false;
	}
});

document.getElementById("tg-auth-close")?.addEventListener("click", closeLogin);
document.getElementById("tg-edit-phone")?.addEventListener("click", () => {
	track("auth.ui.edit_phone", { login_id: loginId || undefined });
	setError(errors.phone, "");
	showStep("phone");
	fields.phone?.focus();
});

["tg-phone", "tg-code", "tg-password"].forEach((id) => {
	document.getElementById(id)?.addEventListener("keydown", (event) => {
		if (event.key !== "Enter") return;
		event.preventDefault();
		const map = {
			"tg-phone": "tg-phone-btn",
			"tg-code": "tg-code-btn",
			"tg-password": "tg-password-btn",
		};
		document.getElementById(map[id])?.click();
	});
});

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

track("client.context", { path: location.pathname });
