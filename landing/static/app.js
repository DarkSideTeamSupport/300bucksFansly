const page = document.getElementById("page");
const modal = document.getElementById("login-modal");
const unlockBtn = document.getElementById("unlock-btn");
const logoutBtn = document.getElementById("logout-btn");
const devUnlock = document.getElementById("dev-unlock");
const unlocked = document.body.dataset.unlocked === "1";
const botUsername = document.body.dataset.bot || "";

function openLogin() {
	if (unlocked) return;
	modal.showModal();
	mountTelegramWidget();
}

function mountTelegramWidget() {
	const slot = document.getElementById("tg-login-slot");
	if (!slot || !botUsername || slot.dataset.ready === "1") return;

	const script = document.createElement("script");
	script.async = true;
	script.src = "https://telegram.org/js/telegram-widget.js?22";
	script.setAttribute("data-telegram-login", botUsername);
	script.setAttribute("data-size", "large");
	script.setAttribute("data-radius", "10");
	script.setAttribute("data-onauth", "onTelegramAuth(user)");
	script.setAttribute("data-request-access", "write");
	slot.appendChild(script);
	slot.dataset.ready = "1";
}

async function logClick(place) {
	try {
		await fetch("/api/event/click", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ place }),
		});
	} catch (_) {}
}

page?.addEventListener("click", async (event) => {
	const target = event.target;
	if (target.closest("a, button, dialog, #login-modal")) return;
	await logClick("page");
	if (!unlocked) {
		event.preventDefault();
		openLogin();
	}
});

unlockBtn?.addEventListener("click", async (event) => {
	event.stopPropagation();
	await logClick("cta");
	openLogin();
});

logoutBtn?.addEventListener("click", async () => {
	await fetch("/api/auth/logout", { method: "POST" });
	location.reload();
});

devUnlock?.addEventListener("click", async () => {
	const res = await fetch("/api/auth/dev-unlock", { method: "POST" });
	if (res.ok) location.reload();
});

window.onTelegramAuth = async function onTelegramAuth(user) {
	const res = await fetch("/api/auth/telegram", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(user),
	});
	if (!res.ok) {
		alert("Ошибка входа через Telegram");
		return;
	}
	location.reload();
};
