export interface AccountDeletionPort {
  request(): Promise<string>;
}

export async function requestAccountDataDeletion(port: AccountDeletionPort) {
  const id = await port.request();
  return { id, status: "running" as const };
}
