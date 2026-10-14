// The console's JSON API (src/console.py). Every call either resolves to the server's JSON or
// rejects with an Error whose message an operator can read.

export async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok && response.status !== 400 && response.status !== 404) {
    throw new Error(`the console answered ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok && response.status !== 400) throw new Error(`the console answered ${response.status}`);
  return (await response.json()) as T;
}

export function message(error: unknown): string {
  return `the console did not answer: ${error instanceof Error ? error.message : String(error)}`;
}
