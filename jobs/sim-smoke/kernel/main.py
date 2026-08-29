# sim-smoke: シード固定の最小社会シミュレーション (Schelling 分居モデル 1971)
#
# cloud-autopilot が「シミュレーターを無料枠クラウドへ運んで実行し、証跡を持ち帰る」
# ことを実証するサンプル。シードが同じなら環境が違っても同じ結果になる (再現性)。
# GPU 環境なら割当も記録する (無くても失敗にはしない。GPU はこのモデルには不要)。
import json
import random
import subprocess
from datetime import datetime, timezone

SEED = 42
SIZE = 20          # 20x20 グリッド
EMPTY_RATIO = 0.10
THRESHOLD = 0.30   # 近傍の同類率がこれ未満なら「不満」で転居する
MAX_STEPS = 120


def build_grid(rng: random.Random) -> list[list[int]]:
    # 0=空地 / 1,2=2 種の住民。住民は半々
    cells = []
    for _ in range(SIZE * SIZE):
        cells.append(0 if rng.random() < EMPTY_RATIO else rng.choice([1, 2]))
    return [cells[i * SIZE : (i + 1) * SIZE] for i in range(SIZE)]


def neighbors(grid, x: int, y: int) -> list[int]:
    out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < SIZE and 0 <= ny < SIZE:
                out.append(grid[ny][nx])
    return out

def same_type_ratio(grid, x: int, y: int) -> float:
    me = grid[y][x]
    around = [v for v in neighbors(grid, x, y) if v != 0]
    if not around:
        return 1.0  # 周囲に誰もいなければ不満は生じない
    return sum(1 for v in around if v == me) / len(around)


def unhappy_cells(grid) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(SIZE)
        for x in range(SIZE)
        if grid[y][x] != 0 and same_type_ratio(grid, x, y) < THRESHOLD
    ]


def run_simulation() -> dict:
    rng = random.Random(SEED)
    grid = build_grid(rng)
    steps = 0
    for steps in range(1, MAX_STEPS + 1):
        unhappy = unhappy_cells(grid)
        if not unhappy:
            break
        empties = [(x, y) for y in range(SIZE) for x in range(SIZE) if grid[y][x] == 0]
        rng.shuffle(unhappy)
        for x, y in unhappy:
            if not empties:
                break
            ex, ey = empties.pop(rng.randrange(len(empties)))
            grid[ey][ex], grid[y][x] = grid[y][x], 0
            empties.append((x, y))
    occupied = [(x, y) for y in range(SIZE) for x in range(SIZE) if grid[y][x] != 0]
    segregation = sum(same_type_ratio(grid, x, y) for x, y in occupied) / len(occupied)
    return {
        "model": "schelling-segregation",
        "seed": SEED,
        "grid": f"{SIZE}x{SIZE}",
        "threshold": THRESHOLD,
        "steps": steps,
        "unhappy_remaining": len(unhappy_cells(grid)),
        "segregation_index": round(segregation, 4),
    }


def probe_gpu() -> str | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=60,
        )
        return (out.stdout.strip() or out.stderr.strip()) or None
    except Exception:
        return None  # GPU 無し環境 (local fallback 等) は正常系


if __name__ == "__main__":
    result = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gpu": probe_gpu(),
        **run_simulation(),
    }
    print(json.dumps(result, ensure_ascii=False))
    with open("sim_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
