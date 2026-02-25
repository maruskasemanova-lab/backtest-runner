type Props = {
  error: string | null | undefined;
  notice: string | null | undefined;
  unifiedError: string | null | undefined;
  profileError: string | null | undefined;
  comboError: string | null | undefined;
};

export default function AdaptiveStudioNotices({
  error,
  notice,
  unifiedError,
  profileError,
  comboError,
}: Props) {
  if (!(error || notice || unifiedError || profileError || comboError)) {
    return null;
  }

  return (
    <div className="adaptive-column" style={{ gap: 6 }}>
      {error && <div className="adaptive-error">{error}</div>}
      {notice && <div className="adaptive-notice">{notice}</div>}
      {unifiedError && <div className="adaptive-error">{unifiedError}</div>}
      {profileError && <div className="adaptive-error">{profileError}</div>}
      {comboError && <div className="adaptive-error">{comboError}</div>}
    </div>
  );
}
