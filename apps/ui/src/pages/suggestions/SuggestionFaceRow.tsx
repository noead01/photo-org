import { type SuggestedFace } from "./types";
import { formatConfidence } from "./formatting";

type SuggestionFaceRowProps = {
  face: SuggestedFace;
  faceNumber: number;
  isSelected: boolean;
  isLoading: boolean;
  isConfirming: boolean;
  isFaceActionInFlight: boolean;
  choiceDraft: string;
  onToggleSelected: (faceId: string) => void;
  onChoiceChange: (faceId: string, value: string) => void;
  onConfirmFace: (face: SuggestedFace) => void;
  onMarkUnknown: (face: SuggestedFace) => void;
  onDismissFalsePositive: (face: SuggestedFace) => void;
};

export function SuggestionFaceRow({
  face,
  faceNumber,
  isSelected,
  isLoading,
  isConfirming,
  isFaceActionInFlight,
  choiceDraft,
  onToggleSelected,
  onChoiceChange,
  onConfirmFace,
  onMarkUnknown,
  onDismissFalsePositive,
}: SuggestionFaceRowProps) {
  const availableSuggestions = (
    Array.isArray(face.suggestions) && face.suggestions.length > 0
      ? face.suggestions
      : [{ ...face.top_suggestion, rank: 1 }]
  )
    .slice()
    .sort((left, right) => {
      if (right.confidence !== left.confidence) {
        return right.confidence - left.confidence;
      }
      const leftRank = typeof left.rank === "number" ? left.rank : Number.MAX_SAFE_INTEGER;
      const rightRank = typeof right.rank === "number" ? right.rank : Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return left.display_name.localeCompare(right.display_name);
    });
  const faceChoiceListId = `suggestions-face-choice-${face.face_id}`;

  return (
    <li>
      <label className="suggestions-face-choice-row">
        <input
          type="checkbox"
          aria-label={`Confirm suggestion for face ${face.face_id}`}
          checked={isSelected}
          onChange={() => onToggleSelected(face.face_id)}
          disabled={isLoading || isConfirming || isFaceActionInFlight}
        />
        <span>{`Face ${faceNumber}`}</span>
        <input
          list={faceChoiceListId}
          value={choiceDraft}
          onChange={(event) => {
            onChoiceChange(face.face_id, event.currentTarget.value);
          }}
          disabled={isLoading || isConfirming || isFaceActionInFlight}
          aria-label={`Choose suggestion for face ${face.face_id}`}
          className="suggestions-face-choice-input"
        />
        <datalist id={faceChoiceListId}>
          {availableSuggestions.map((suggestion) => (
            <option
              key={`${face.face_id}-${suggestion.person_id}`}
              value={suggestion.display_name}
            >
              {formatConfidence(suggestion.confidence)}
            </option>
          ))}
        </datalist>
      </label>
      <div className="suggestions-face-actions">
        <button
          type="button"
          className="suggestions-face-confirm-button"
          onClick={() => onConfirmFace(face)}
          disabled={isLoading || isConfirming || isFaceActionInFlight}
        >
          Confirm face
        </button>
        <button
          type="button"
          className="suggestions-face-secondary-button"
          onClick={() => onMarkUnknown(face)}
          disabled={isLoading || isConfirming || isFaceActionInFlight}
          aria-label={`Mark face ${face.face_id} as unknown`}
        >
          Mark unknown
        </button>
        <button
          type="button"
          className="suggestions-face-secondary-button"
          onClick={() => onDismissFalsePositive(face)}
          disabled={isLoading || isConfirming || isFaceActionInFlight}
          aria-label={`Discard face ${face.face_id} as false positive`}
        >
          False positive
        </button>
      </div>
    </li>
  );
}
