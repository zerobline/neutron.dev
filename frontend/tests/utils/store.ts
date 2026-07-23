import { useProjectStore } from "@/stores/project-store";

export function resetProjectStore() {
  useProjectStore.getState().reset();
}
