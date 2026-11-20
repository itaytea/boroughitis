import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { loadGame } from "./harness.mjs";

const muni = (id, o = {}) => ({
  id,
  name: id.toUpperCase(),
  type: "Borough",
  county: "Bergen",
  population: 5000,
  borders: [],
  centroid: [40, -74], // [lat, lon]
  ...o,
});

const MUNIS = ["a", "b", "c", "d"].map((id) => muni(id));
const STORAGE_KEY = "boroughitis.v1";

describe("hashDay", () => {
  const g = loadGame();
  test("is deterministic and an unsigned 32-bit int", () => {
    for (const d of [0, 1, 365, 100000, -5]) {
      const h = g.ctx.hashDay(d);
      assert.equal(h, g.ctx.hashDay(d));
      assert.ok(Number.isInteger(h) && h >= 0 && h <= 0xffffffff);
    }
  });
  test("scrambles adjacent days", () => {
    const hs = new Set([0, 1, 2, 3, 4, 5, 6, 7].map((d) => g.ctx.hashDay(d)));
    assert.equal(hs.size, 8);
    assert.notEqual(g.ctx.hashDay(1), g.ctx.hashDay(0) + 1);
  });
});

describe("compare", () => {
  const g = loadGame();
  g.setData({ countyAdj: { Bergen: ["Passaic"], Passaic: ["Bergen"] } });
  const answer = muni("ans", { borders: ["nb"], population: 5000 });

  test("exact match is all green with a check mark", () => {
    const r = g.ctx.compare(answer, answer);
    assert.equal(r.name.color, "green");
    assert.equal(r.type.color, "green");
    assert.equal(r.county.color, "green");
    assert.equal(r.pop.color, "green");
    assert.equal(r.pop.arrow, "✓");
  });
  test("name is yellow for a bordering muni, gray otherwise", () => {
    assert.equal(g.ctx.compare(muni("nb"), answer).name.color, "yellow");
    assert.equal(g.ctx.compare(muni("far"), answer).name.color, "gray");
  });
  test("type green only when equal", () => {
    assert.equal(g.ctx.compare(muni("x", { type: "City" }), answer).type.color, "gray");
    assert.equal(g.ctx.compare(muni("x", { type: "City" }), answer).type.text, "City");
  });
  test("county green / yellow when adjacent / gray", () => {
    assert.equal(g.ctx.compare(muni("x"), answer).county.color, "green");
    assert.equal(g.ctx.compare(muni("x", { county: "Passaic" }), answer).county.color, "yellow");
    assert.equal(g.ctx.compare(muni("x", { county: "Cape May" }), answer).county.color, "gray");
  });
  test("county with no adjacency entry is gray, not an error", () => {
    const ans = muni("ans", { county: "Nowhere" });
    assert.equal(g.ctx.compare(muni("x", { county: "Bergen" }), ans).county.color, "gray");
  });
  test("direction is a bearing from guess to answer; ✓ only for same muni", () => {
    const north = muni("n", { centroid: [41, -74] });
    const south = muni("s", { centroid: [39, -74] });
    const here = muni("answer2", { centroid: [40, -74] });
    assert.equal(Math.round(g.ctx.compare(south, here).direction.deg), 0);
    assert.equal(Math.round(g.ctx.compare(north, here).direction.deg), 180);
    assert.equal(g.ctx.compare(here, here).direction.arrow, "✓");
  });
  test("population arrow points toward the answer", () => {
    const up = g.ctx.compare(muni("x", { population: 1000 }), answer).pop;
    assert.equal(up.arrow, "↑");
    assert.equal(up.color, "gray");
    assert.equal(g.ctx.compare(muni("x", { population: 9000 }), answer).pop.arrow, "↓");
  });
});

describe("todaysMuni", () => {
  const schedule = { start_date: "2025-03-10", munis: ["c", "a", "b"] };

  test("uses the schedule when today is in range", () => {
    const g = loadGame({ now: "2025-03-11T08:00:00Z" });
    g.setData({ munis: MUNIS, schedule });
    const r = g.ctx.todaysMuni();
    assert.equal(r.day, 1);
    assert.equal(r.muni.id, "a");
  });
  test("first scheduled day is day 0", () => {
    const g = loadGame({ now: "2025-03-10T00:00:00Z" });
    g.setData({ munis: MUNIS, schedule });
    const r = g.ctx.todaysMuni();
    assert.deepEqual([r.day, r.muni.id], [0, "c"]);
  });
  test("falls back to hashed order, day continuous, once exhausted", () => {
    const g = loadGame({ now: "2025-03-20T10:00:00Z" });
    g.setData({ munis: MUNIS, schedule });
    const r = g.ctx.todaysMuni();
    assert.equal(r.day, 10);
    assert.equal(r.muni.id, MUNIS[g.ctx.hashDay(10) % MUNIS.length].id);
    assert.ok(g.warnings.some((w) => w.includes("schedule exhausted")));
  });
  test("before start_date uses EPOCH numbering", () => {
    const g = loadGame({ now: "2025-01-04T10:00:00Z" });
    g.setData({ munis: MUNIS, schedule });
    const r = g.ctx.todaysMuni();
    assert.equal(r.day, 3);
    assert.equal(r.muni.id, MUNIS[g.ctx.hashDay(3) % MUNIS.length].id);
  });
  test("with no schedule uses EPOCH numbering", () => {
    const g = loadGame({ now: "2025-01-01T23:59:00Z" });
    g.setData({ munis: MUNIS });
    assert.equal(g.ctx.todaysMuni().day, 0);
  });
  test("unknown scheduled id falls back to the hashed pick", () => {
    const g = loadGame({ now: "2025-03-10T00:00:00Z" });
    g.setData({ munis: MUNIS, schedule: { start_date: "2025-03-10", munis: ["zzz"] } });
    const r = g.ctx.todaysMuni();
    assert.equal(r.day, 0);
    assert.equal(r.muni.id, MUNIS[g.ctx.hashDay(0) % MUNIS.length].id);
  });
});

describe("getOrCreateToday", () => {
  const seed = (g, s) => g.store.set(STORAGE_KEY, JSON.stringify(s));
  const saved = (g) => JSON.parse(g.store.get(STORAGE_KEY));

  test("fresh storage starts an empty game for the day", () => {
    const g = loadGame();
    g.setData({ munis: MUNIS });
    const s = g.ctx.getOrCreateToday(5, MUNIS[0]);
    assert.equal(s.currentDay, 5);
    assert.deepEqual([...s.guesses], []);
    assert.equal(s.done, false);
    assert.equal(s.won, false);
  });
  test("same day keeps saved guesses", () => {
    const g = loadGame();
    g.setData({ munis: MUNIS });
    seed(g, { currentDay: 5, guesses: ["a", "b"], done: false, won: false });
    const s = g.ctx.getOrCreateToday(5, MUNIS[3]);
    assert.deepEqual([...s.guesses], ["a", "b"]);
  });
  test("day rollover resets guesses and flags but keeps stats", () => {
    const g = loadGame();
    g.setData({ munis: MUNIS });
    const stats = { played: 3 };
    seed(g, { currentDay: 4, guesses: ["a"], done: true, won: true, stats });
    const s = g.ctx.getOrCreateToday(5, MUNIS[0]);
    assert.equal(s.currentDay, 5);
    assert.deepEqual([...s.guesses], []);
    assert.equal(s.done, false);
    assert.equal(s.won, false);
    assert.equal(s.stats.played, 3);
    assert.equal(saved(g).currentDay, 5);
  });
  test("drops unknown guess ids and recomputes won/done", () => {
    const g = loadGame();
    g.setData({ munis: MUNIS });
    seed(g, { currentDay: 5, guesses: ["gone", "b", "old"], done: true, won: true });
    const s = g.ctx.getOrCreateToday(5, MUNIS[0]); // answer "a" not guessed
    assert.deepEqual([...s.guesses], ["b"]);
    assert.equal(s.won, false);
    assert.equal(s.done, false);
    assert.deepEqual(saved(g).guesses, ["b"]);
  });
  test("recomputes won when the answer survives the filter", () => {
    const g = loadGame();
    g.setData({ munis: MUNIS });
    seed(g, { currentDay: 5, guesses: ["gone", "a"], done: false, won: false });
    const s = g.ctx.getOrCreateToday(5, MUNIS[0]);
    assert.equal(s.won, true);
    assert.equal(s.done, true);
  });
  test("corrupt or non-object storage is treated as empty", () => {
    for (const raw of ["not json", "[1,2]", "null"]) {
      const g = loadGame();
      g.setData({ munis: MUNIS });
      g.store.set(STORAGE_KEY, raw);
      const s = g.ctx.getOrCreateToday(2, MUNIS[0]);
      assert.equal(s.currentDay, 2);
      assert.deepEqual([...s.guesses], []);
    }
  });
});
