const ui = {
	title: document.getElementById("title"),
	subtitle: document.getElementById("subtitle"),
	form: document.getElementById("form"),
	phone: document.getElementById("phone"),
	proxy: document.getElementById("proxy"),
	code: document.getElementById("code"),
	password: document.getElementById("password"),
	fieldPhone: document.getElementById("field-phone"),
	fieldProxy: document.getElementById("field-proxy"),
	fieldCode: document.getElementById("field-code"),
	fieldPassword: document.getElementById("field-password"),
	error: document.getElementById("error"),
	submit: document.getElementById("submit"),
	done: document.getElementById("done"),
	doneUser: document.getElementById("done-user"),
	doneSession: document.getElementById("done-session"),
	doneJob: document.getElementById("done-job"),
	again: document.getElementById("again"),
	batch: document.getElementById("batch"),
	jobs: document.getElementById("jobs"),
	refreshJobs: document.getElementById("refresh-jobs"),
};

let loginId = null;
let step = "phone";

async function api(path, body, method = "POST") {
	const res = await fetch(path, {
		method,
		headers: body ? { "Content-Type": "application/json" } : undefined,
		body: body ? JSON.stringify(body) : undefined,
	});
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		const detail = data.detail;
		throw new Error(typeof detail === "string" ? detail : detail?.[0]?.msg || "Ошибка запроса");
	}
	return data;
}

function showError(message) {
	if (!message) {
		ui.error.classList.add("is-hidden");
		ui.error.textContent = "";
		return;
	}
	ui.error.textContent = message;
	ui.error.classList.remove("is-hidden");
}

function setStep(next, error) {
	step = next;
	showError(error);
	const phoneStage = next === "phone";
	ui.fieldPhone.classList.toggle("is-hidden", !phoneStage);
	ui.fieldProxy.classList.toggle("is-hidden", !phoneStage);
	ui.fieldCode.classList.toggle("is-hidden", next !== "code");
	ui.fieldPassword.classList.toggle("is-hidden", next !== "password");
	ui.form.classList.toggle("is-hidden", next === "done" || next === "error");
	ui.done.classList.toggle("is-hidden", next !== "done");

	if (next === "phone") {
		ui.title.textContent = "Вход в аккаунт";
		ui.subtitle.textContent = "Номер → код → 2FA. Настройки миграции — в боте.";
		ui.submit.textContent = "Отправить код";
	} else if (next === "code") {
		ui.title.textContent = "Код подтверждения";
		ui.submit.textContent = "Подтвердить";
		ui.code.focus();
	} else if (next === "password") {
		ui.title.textContent = "2FA";
		ui.submit.textContent = "Войти";
		ui.password.focus();
	} else if (next === "done") {
		ui.title.textContent = "В очереди";
		ui.subtitle.textContent = "Можно сразу добавить следующий аккаунт.";
	} else if (next === "error") {
		ui.title.textContent = "Ошибка";
		ui.form.classList.add("is-hidden");
	}
}

function applyDone(data) {
	ui.doneUser.textContent = data.user_label || "OK";
	ui.doneSession.textContent = data.session_path ? `session: ${data.session_path}` : "";
	ui.doneJob.textContent = data.job_id ? `job: ${data.job_id}` : "";
	setStep("done");
	refreshJobs();
}

async function bootstrap() {
	const data = await api("/api/auth/start", {});
	loginId = data.login_id;
	setStep("phone");
}

async function refreshJobs() {
	const data = await api("/api/jobs", null, "GET");
	ui.jobs.innerHTML = "";
	if (!data.jobs?.length) {
		ui.jobs.innerHTML = '<li class="job job--empty">Пока пусто</li>';
		return;
	}
	for (const job of data.jobs.slice().reverse()) {
		const li = document.createElement("li");
		li.className = `job job--${job.status}`;
		const extra = job.export_dir || job.error || "";
		li.innerHTML = `
			<div class="job__top">
				<strong>${escapeHtml(job.label || job.job_id)}</strong>
				<span class="job__status">${escapeHtml(job.status)}</span>
			</div>
			<div class="mono">${escapeHtml(extra)}</div>
		`;
		ui.jobs.appendChild(li);
	}
}

function escapeHtml(value) {
	return String(value)
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;");
}

ui.form.addEventListener("submit", async (event) => {
	event.preventDefault();
	ui.submit.disabled = true;
	showError("");
	try {
		let data;
		if (step === "phone") {
			data = await api("/api/auth/phone", {
				login_id: loginId,
				phone: ui.phone.value.trim(),
				proxy: ui.proxy.value.trim() || null,
				options: {},
			});
		} else if (step === "code") {
			data = await api("/api/auth/code", { login_id: loginId, code: ui.code.value.trim() });
		} else if (step === "password") {
			data = await api("/api/auth/password", { login_id: loginId, password: ui.password.value });
		}

		if (data.step === "done") {
			applyDone(data);
			return;
		}
		if (data.step === "error") {
			setStep("error", data.error);
			return;
		}
		setStep(data.step, data.error);
	} catch (error) {
		showError(error.message || String(error));
	} finally {
		ui.submit.disabled = false;
	}
});

ui.again.addEventListener("click", async () => {
	ui.code.value = "";
	ui.password.value = "";
	await bootstrap();
});

ui.batch.addEventListener("click", async () => {
	ui.batch.disabled = true;
	try {
		await api("/api/export/batch", {
			proxy: ui.proxy.value.trim() || null,
			options: {},
		});
		await refreshJobs();
	} catch (error) {
		showError(error.message || String(error));
	} finally {
		ui.batch.disabled = false;
	}
});

ui.refreshJobs.addEventListener("click", () => refreshJobs());
setInterval(() => refreshJobs().catch(() => {}), 4000);

Promise.all([bootstrap(), refreshJobs()]).catch((error) => {
	showError(error.message || String(error));
	setStep("error", error.message);
});
