import { useCallback, useEffect, useState } from "react";
import {
  signInWithGoogle,
  signOutSupabase,
  subscribeAuthSnapshot,
} from "../auth/supabaseAuth";
import { EMPTY_AUTH_SNAPSHOT } from "../app/appShared";

type UseAppAuthStateArgs = {
  setRuntimeNotice: (notice: string) => void;
};

export const useAppAuthState = ({
  setRuntimeNotice,
}: UseAppAuthStateArgs) => {
  const [authSnapshot, setAuthSnapshot] = useState(EMPTY_AUTH_SNAPSHOT);
  const [authActionBusy, setAuthActionBusy] = useState(false);

  useEffect(() => {
    const unsubscribe = subscribeAuthSnapshot((snapshot) => {
      setAuthSnapshot(snapshot);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  const handleAuthSignIn = useCallback(async () => {
    if (authActionBusy) return;
    setAuthActionBusy(true);
    setRuntimeNotice("");
    try {
      await signInWithGoogle();
    } catch (error) {
      console.error("Google sign-in failed:", error);
      setRuntimeNotice("Google sign-in failed.");
    } finally {
      setAuthActionBusy(false);
    }
  }, [authActionBusy, setRuntimeNotice]);

  const handleAuthSignOut = useCallback(async () => {
    if (authActionBusy) return;
    setAuthActionBusy(true);
    setRuntimeNotice("");
    try {
      await signOutSupabase();
    } catch (error) {
      console.error("Sign-out failed:", error);
      setRuntimeNotice("Sign-out failed.");
    } finally {
      setAuthActionBusy(false);
    }
  }, [authActionBusy, setRuntimeNotice]);

  return {
    authActionBusy,
    authSnapshot,
    handleAuthSignIn,
    handleAuthSignOut,
  };
};
