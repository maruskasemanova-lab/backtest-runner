import type { Dispatch, SetStateAction } from "react";
import { useEventCallback } from "usehooks-ts";

import {
  createDefaultMomentumSleeveDraft,
  type MomentumSleeveDraft,
} from "./momentumUtils";

interface ConfigWithMomentumSleeves {
  momentum_sleeves?: MomentumSleeveDraft[];
  [key: string]: unknown;
}

type SleeveField = keyof MomentumSleeveDraft;

type SleeveFieldValue = string | number | boolean | null;

export const useMomentumSleeves = <T extends ConfigWithMomentumSleeves>(
  setConfig: Dispatch<SetStateAction<T>>,
) => {
  const handleMomentumSleeveChange = useEventCallback(
    (index: number, field: SleeveField, value: SleeveFieldValue): void => {
      setConfig((prev) => {
        const current = Array.isArray(prev.momentum_sleeves) ? prev.momentum_sleeves : [];
        if (index < 0 || index >= current.length) return prev;
        const next = current.map((item, idx) =>
          idx === index ? { ...(item || {}), [field]: value } : item,
        );
        return { ...prev, momentum_sleeves: next } as T;
      });
    },
  );

  const handleAddMomentumSleeve = useEventCallback((): void => {
    setConfig((prev) => {
      const current = Array.isArray(prev.momentum_sleeves) ? prev.momentum_sleeves : [];
      const draft = createDefaultMomentumSleeveDraft(current.length + 1);
      return { ...prev, momentum_sleeves: [...current, draft] } as T;
    });
  });

  const handleRemoveMomentumSleeve = useEventCallback((index: number): void => {
    setConfig((prev) => {
      const current = Array.isArray(prev.momentum_sleeves) ? prev.momentum_sleeves : [];
      if (index < 0 || index >= current.length) return prev;
      return {
        ...prev,
        momentum_sleeves: current.filter((_, idx) => idx !== index),
      } as T;
    });
  });

  return {
    handleMomentumSleeveChange,
    handleAddMomentumSleeve,
    handleRemoveMomentumSleeve,
  };
};
