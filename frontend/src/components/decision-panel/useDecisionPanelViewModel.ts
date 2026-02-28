import { useMemo } from "react";
import {
  buildDecisionPanelViewModel,
  type UseDecisionPanelViewModelParams,
} from "./buildDecisionPanelViewModel";

export default function useDecisionPanelViewModel({
  selectedMarker,
  uiLanguage,
}: UseDecisionPanelViewModelParams) {
  return useMemo(
    () => buildDecisionPanelViewModel(selectedMarker, uiLanguage),
    [selectedMarker, uiLanguage],
  );
}
