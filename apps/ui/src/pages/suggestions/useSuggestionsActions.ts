import { useState, type Dispatch, type SetStateAction } from "react";

import {
  assignFace,
  createPerson,
  dismissFace,
  markFaceUnknown,
} from "../face-labeling/faceLabelingApi";
import { confirmSuggestions } from "./api";
import {
  NOT_A_FACE_CHOICE_LABEL,
  UNKNOWN_FACE_CHOICE_LABEL,
  type FaceChoiceResolution,
  type PersonRecord,
  type SuggestionPhoto,
  type SuggestedFace,
} from "./types";

type UseSuggestionsActionsArgs = {
  isLoading: boolean;
  page: number;
  payloadItems: SuggestionPhoto[];
  peopleDirectory: PersonRecord[];
  currentPageFaceIdsOrdered: string[];
  selectedFaceIds: Set<string>;
  faceChoiceDrafts: Map<string, string>;
  loadPage: (page: number) => Promise<void>;
  setPeopleDirectory: Dispatch<SetStateAction<PersonRecord[]>>;
};

function resolveFaceChoice(
  face: SuggestedFace,
  rawChoice: string,
  peopleDirectory: PersonRecord[]
): FaceChoiceResolution {
  const trimmedChoice = rawChoice.trim();
  if (trimmedChoice.length === 0) {
    return { kind: "empty" };
  }

  const normalizedChoice = trimmedChoice.toLowerCase();
  if (normalizedChoice === UNKNOWN_FACE_CHOICE_LABEL.toLowerCase()) {
    return { kind: "unknown_human" };
  }
  if (normalizedChoice === NOT_A_FACE_CHOICE_LABEL.toLowerCase()) {
    return { kind: "dismiss_false_positive" };
  }

  const suggestionMatch = face.suggestions.find(
    (suggestion) => suggestion.display_name.toLowerCase() === normalizedChoice
  );
  if (suggestionMatch) {
    return { kind: "assign_person", personId: suggestionMatch.person_id };
  }

  const personMatch = peopleDirectory.find(
    (person) => person.display_name.toLowerCase() === normalizedChoice
  );
  if (personMatch) {
    return { kind: "assign_person", personId: personMatch.person_id };
  }

  return { kind: "create_person_and_assign", displayName: trimmedChoice };
}

export function useSuggestionsActions({
  isLoading,
  page,
  payloadItems,
  peopleDirectory,
  currentPageFaceIdsOrdered,
  selectedFaceIds,
  faceChoiceDrafts,
  loadPage,
  setPeopleDirectory,
}: UseSuggestionsActionsArgs) {
  const [isConfirming, setIsConfirming] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [faceActionInFlightIds, setFaceActionInFlightIds] = useState<Set<string>>(new Set());

  async function runFaceAction(
    faceId: string,
    action: () => Promise<void>,
    fallbackErrorMessage: string
  ) {
    if (isLoading || isConfirming || faceActionInFlightIds.has(faceId)) {
      return;
    }

    setFaceActionInFlightIds((current) => new Set(current).add(faceId));
    setMessage(null);
    try {
      await action();
      await loadPage(page);
    } catch (caughtError: unknown) {
      setMessage(
        caughtError instanceof Error && caughtError.message.trim().length > 0
          ? caughtError.message
          : fallbackErrorMessage
      );
    } finally {
      setFaceActionInFlightIds((current) => {
        const next = new Set(current);
        next.delete(faceId);
        return next;
      });
    }
  }

  async function submitDismissFalsePositive(faceId: string) {
    await dismissFace(faceId);
  }

  async function submitUnknownHuman(faceId: string) {
    await markFaceUnknown(faceId);
  }

  async function handleConfirmFaces() {
    if (isConfirming || currentPageFaceIdsOrdered.length === 0) {
      return;
    }

    setIsConfirming(true);
    setMessage(null);
    try {
      const faceById = new Map(
        payloadItems.flatMap((photo) => photo.faces.map((face) => [face.face_id, face] as const))
      );
      const selectedAssignments = currentPageFaceIdsOrdered
        .filter((faceId) => selectedFaceIds.has(faceId))
        .map((faceId) => {
          const face = faceById.get(faceId);
          if (!face) {
            return null;
          }
          const draft = faceChoiceDrafts.get(faceId) ?? face.top_suggestion.display_name;
          const resolution = resolveFaceChoice(face, draft, peopleDirectory);
          if (resolution.kind !== "assign_person") {
            return null;
          }
          const isSuggested = face.suggestions.some(
            (suggestion) => suggestion.person_id === resolution.personId
          );
          if (!isSuggested) {
            return null;
          }
          return { face_id: faceId, person_id: resolution.personId };
        })
        .filter((value): value is { face_id: string; person_id: string } => value !== null);

      if (selectedAssignments.length === 0) {
        setMessage("No checked faces are set to a suggested person. Use Confirm face for custom actions.");
        return;
      }

      const result = await confirmSuggestions(
        selectedAssignments.map((assignment) => assignment.face_id),
        selectedAssignments
      );
      const assignedCount = result.assigned.length;
      const label = assignedCount === 1 ? "face suggestion" : "face suggestions";
      setMessage(`Confirmed ${assignedCount} ${label}.`);
      await loadPage(page);
    } catch (caughtError: unknown) {
      setMessage(
        caughtError instanceof Error ? caughtError.message : "Could not confirm face suggestions."
      );
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleConfirmSingleFace(face: SuggestedFace) {
    const draft = faceChoiceDrafts.get(face.face_id) ?? face.top_suggestion.display_name;
    const resolution = resolveFaceChoice(face, draft, peopleDirectory);
    if (resolution.kind === "empty") {
      setMessage("Choose or type a value before confirming this face.");
      return;
    }

    if (resolution.kind === "dismiss_false_positive") {
      await runFaceAction(
        face.face_id,
        async () => {
          await submitDismissFalsePositive(face.face_id);
          setMessage("Face flagged as not a face.");
        },
        "Could not flag face as false positive."
      );
      return;
    }

    if (resolution.kind === "unknown_human") {
      await runFaceAction(
        face.face_id,
        async () => {
          await submitUnknownHuman(face.face_id);
          setMessage("Face marked as human with unknown name.");
        },
        "Could not mark face as unknown."
      );
      return;
    }

    await runFaceAction(
      face.face_id,
      async () => {
        let personId = "";
        if (resolution.kind === "create_person_and_assign") {
          const createdPerson = (await createPerson(resolution.displayName)) as PersonRecord;
          personId = createdPerson.person_id;
          setPeopleDirectory((current) => [...current, createdPerson]);
        } else {
          personId = resolution.personId;
        }

        await assignFace(face.face_id, personId);

        setMessage("Face confirmed.");
      },
      "Could not confirm face."
    );
  }

  async function handleMarkFaceUnknown(face: SuggestedFace) {
    await runFaceAction(
      face.face_id,
      async () => {
        await submitUnknownHuman(face.face_id);
        setMessage("Face marked as human with unknown name.");
      },
      "Could not mark face as unknown."
    );
  }

  async function handleDismissFalsePositive(face: SuggestedFace) {
    await runFaceAction(
      face.face_id,
      async () => {
        await submitDismissFalsePositive(face.face_id);
        setMessage("Face flagged as not a face.");
      },
      "Could not flag face as false positive."
    );
  }

  return {
    isConfirming,
    message,
    faceActionInFlightIds,
    setMessage,
    handleConfirmFaces,
    handleConfirmSingleFace,
    handleMarkFaceUnknown,
    handleDismissFalsePositive,
  };
}
