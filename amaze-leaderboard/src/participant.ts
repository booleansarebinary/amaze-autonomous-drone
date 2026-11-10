import type { LeaderboardApi } from "./api";
import { layersHtml } from "./actor";
import { BODY_COLORS, HATS, OUTFITS, type Look } from "./art/characters";
import { escapeHtml } from "./list";
import { fmtError, fmtTimestamp } from "./model";

/** Local operator/participant screen; the target only appears in setup. */
export function renderParticipant(host: HTMLElement, api: LeaderboardApi, setup: boolean) {
  const options = (values: string[]) => values.map(value => `<option>${escapeHtml(value)}</option>`).join("");
  host.innerHTML = `<main class="mission-page">
    <a class="back-link" href="?">← Leaderboard</a>
    <p class="eyebrow">AMAZE · DISTANCE MISSION</p>
    <h1>${setup ? "Mission setup" : "How far will it go?"}</h1>
    <p>${setup ? "Set the correct distance before the first guess. Keep this screen with the mission operator." : "Build your character, enter your distance guess, and see how close you get. Only your best attempt counts."}</p>
    ${setup ? `<form id="setup-form" class="mission-card"><h2>Correct distance</h2>
      <label>Target distance<input id="target" type="number" min="0.000001" step="any" required></label>
      <label>Distance unit<input id="unit" maxlength="12" value="cm" required></label>
      <button>Save mission settings</button><p id="config-status"></p>
      <a href="?view=input">Go to participant entry →</a></form>` : `
    <div class="mission-grid"><section class="mission-card"><h2>Your player</h2>
      <label>Returning player<select id="player"><option value="">Create a new player</option></select></label>
      <button id="new-player" type="button">New player</button>
      <form id="player-form"><label>Display name<input id="name" maxlength="40" autocomplete="off" required></label>
        <div class="avatar-editor"><div class="avatar-preview" aria-label="Avatar preview"><div class="fig"></div></div><div>
        <label>Body color<select id="color">${options(Object.keys(BODY_COLORS))}</select></label>
        <label>Outfit<select id="outfit">${options(Object.keys(OUTFITS))}</select></label>
        <label>Hat<select id="hat">${options(Object.keys(HATS))}</select></label></div></div>
        <button id="save-player">Create player</button></form>
    </section><section class="mission-card"><h2>Your guess</h2><p id="mission-status"></p>
      <form id="guess-form"><label>Distance <span id="distance-unit"></span><input id="guess" type="number" min="0" step="any" required></label>
      <button id="submit-guess">Submit guess</button></form><p id="best"></p>
      <h3>Your attempts</h3><ol id="history" class="attempt-history"></ol>
    </section></div>`}
    <p id="feedback" role="status" aria-live="polite"></p>
    <p id="storage-status" role="alert"></p>
    <footer>Submissions use CST (UTC−6). Your timestamp does not affect your rank.</footer>
  </main>`;
  const q = <T extends HTMLElement>(id: string) => host.querySelector<T>(`#${id}`)!;
  const feedback = (message: string) => { q("feedback").textContent = message; };
  const action = (fn: () => void) => { try { fn(); } catch (error) { feedback(error instanceof Error ? error.message : String(error)); } };

  if (setup) {
    const update = () => {
      const state = api.state();
      q<HTMLInputElement>("target").value = state.targetDistance?.toString() ?? "";
      q<HTMLInputElement>("unit").value = state.unit;
      q<HTMLInputElement>("target").disabled = state.attempts.length > 0;
      q<HTMLInputElement>("unit").disabled = state.attempts.length > 0;
      q("config-status").textContent = state.attempts.length ? "Settings are locked because this mission has submissions." : "Settings lock after the first submission.";
      q("storage-status").textContent = api.storageError;
    };
    q("setup-form").addEventListener("submit", event => {
      event.preventDefault();
      action(() => { api.configure(q<HTMLInputElement>("target").valueAsNumber, q<HTMLInputElement>("unit").value); feedback("Mission settings saved."); });
    });
    api.onChange(update); update();
    return;
  }

  let playerId = "";
  const selector = q<HTMLSelectElement>("player");
  const look = (): Look => ({ color: q<HTMLSelectElement>("color").value, outfit: q<HTMLSelectElement>("outfit").value, hat: q<HTMLSelectElement>("hat").value });
  const preview = () => { host.querySelector(".avatar-preview .fig")!.innerHTML = layersHtml(look()); };
  ["color", "outfit", "hat"].forEach(id => q(id).addEventListener("change", preview));
  const selectPlayer = () => {
    playerId = selector.value;
    q<HTMLFormElement>("guess-form").reset();
    const player = api.state().players.find(p => p.id === playerId);
    q<HTMLInputElement>("name").value = player?.name ?? "";
    for (const key of ["color", "outfit", "hat"] as const) q<HTMLSelectElement>(key).value = player?.look[key] ?? (key === "color" ? "Pink" : "None");
    q("save-player").textContent = player ? "Save player & avatar" : "Create player";
    preview(); update();
  };
  const update = () => {
    const state = api.state();
    if (!state.players.some(p => p.id === playerId)) playerId = "";
    selector.replaceChildren(new Option("Create a new player", ""));
    state.players.forEach((player, i) => {
      const duplicate = state.players.filter(p => p.name === player.name).length > 1;
      selector.add(new Option(`${player.name}${duplicate ? ` (player ${i + 1})` : ""}`, player.id));
    });
    selector.value = playerId;
    const configured = state.targetDistance !== null;
    q("mission-status").textContent = !configured ? "The operator needs to configure this mission before guesses can begin." : !playerId ? "Create or select your player before submitting a guess." : "Take another guess any time. Your best result stays on the leaderboard.";
    q("distance-unit").textContent = `(${state.unit})`;
    q<HTMLButtonElement>("submit-guess").disabled = !configured || !playerId;
    const best = api.players().find(p => p.id === playerId);
    const attempts = state.attempts.filter(a => a.playerId === playerId);
    // A player outside the displayed top 20 still has a personal best.
    const bestAttempt = attempts.reduce<typeof attempts[number] | undefined>((current, a) => !current || a.error < current.error ? a : current, undefined);
    q("best").textContent = bestAttempt ? `Best: ${fmtError(bestAttempt.error)}${best ? ` · Rank ${best.rank}` : ""} · ${fmtTimestamp(bestAttempt.submittedAt)} CST` : "No attempts yet.";
    q("history").replaceChildren(...attempts.slice().reverse().map(attempt => {
      const item = document.createElement("li");
      item.textContent = `${attempt.guess === undefined ? "Imported score" : `${attempt.guess} ${state.unit}`} · ${fmtError(attempt.error)} · ${fmtTimestamp(attempt.submittedAt)} CST`;
      return item;
    }));
    q("storage-status").textContent = api.storageError;
  };
  const newPlayer = () => {
    selector.value = "";
    selectPlayer();
    q<HTMLInputElement>("name").focus();
  };
  q("new-player").addEventListener("click", () => {
    newPlayer();
    feedback("Ready for a new player. Returning players can select their name above.");
  });
  selector.addEventListener("change", selectPlayer);
  q("player-form").addEventListener("submit", event => {
    event.preventDefault();
    action(() => {
      const player = api.registerPlayer(q<HTMLInputElement>("name").value, look(), playerId || undefined);
      playerId = player.id; selector.value = playerId; selectPlayer(); feedback(`Ready, ${player.name}. Your player has been saved.`);
    });
  });
  q("guess-form").addEventListener("submit", event => {
    event.preventDefault();
    action(() => {
      const attempt = api.submitGuess(playerId, q<HTMLInputElement>("guess").valueAsNumber);
      newPlayer();
      feedback(`Submitted at ${fmtTimestamp(attempt.submittedAt)} CST: ${fmtError(attempt.error)} error. Your best attempt is on the leaderboard. Ready for the next player; select your name above to try again.`);
    });
  });
  api.onChange(update); selectPlayer();
}
