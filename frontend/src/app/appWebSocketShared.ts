type RunMessageLike = {
  type?: string;
  run_key?: string;
  run_id?: string;
  ticker?: string;
  date?: string;
};

type ActiveRunIdentity = {
  runKey: string | null;
  runId: string | null;
  ticker: string | null;
  date: string | null;
};

export const isRunStreamMessageRelevant = (
  message: RunMessageLike | null | undefined,
  activeRun: ActiveRunIdentity,
): boolean => {
  const msgRunKey = message?.run_key ? String(message.run_key) : null;
  const msgRunId = message?.run_id ? String(message.run_id) : null;
  const msgTicker = message?.ticker ? String(message.ticker).toUpperCase() : null;
  const msgDate = message?.date ? String(message.date) : null;
  const activeTicker = activeRun.ticker ? String(activeRun.ticker).toUpperCase() : null;

  if (activeRun.runKey && msgRunKey && msgRunKey !== activeRun.runKey) return false;
  if (activeRun.runId && msgRunId && msgRunId !== activeRun.runId) return false;
  if (activeTicker && msgTicker && msgTicker !== activeTicker) return false;
  if (activeRun.date && msgDate && msgDate !== activeRun.date) return false;
  return true;
};

export const shouldQueueVisibilitySyncMessage = (
  message: RunMessageLike | null | undefined,
  isVisible: boolean,
): boolean => {
  if (isVisible) return false;
  return message?.type === 'bar' || message?.type === 'decision';
};
