import { useMemo, useState } from "react";
import type { PhotoDetailPayload } from "./photoDetailTypes";
import {
  MISSING_VALUE,
  formatExifAttributeValue,
  formatFilesize,
  formatGps,
  formatOptionalText,
  formatTimestamp,
} from "./photoDetailFormatting";

type IngestStatus = {
  tone: "complete" | "pending" | "failed" | "unknown";
  label: string;
  description: string;
} | null;

interface PhotoMetadataFlyoutProps {
  detail: PhotoDetailPayload;
  ingestStatus: IngestStatus;
  isOpen: boolean;
  onClose: () => void;
}

export function PhotoMetadataFlyout({
  detail,
  ingestStatus,
  isOpen,
  onClose,
}: PhotoMetadataFlyoutProps) {
  const [isExifAttributesOpen, setIsExifAttributesOpen] = useState(false);
  const facesLabel = useMemo(() => {
    const count = detail.metadata.faces_count;
    return count === 1 ? "1 detected" : `${count} detected`;
  }, [detail.metadata.faces_count]);
  const exifAttributeEntries = useMemo(() => {
    const attributes = detail.metadata.exif_attributes;
    if (!attributes) {
      return [] as Array<[string, unknown]>;
    }
    return Object.entries(attributes).sort(([leftName], [rightName]) =>
      leftName.localeCompare(rightName, "en-US")
    );
  }, [detail.metadata.exif_attributes]);

  return (
    <>
      <button
        type="button"
        className={`detail-flyout-backdrop${isOpen ? " is-open" : ""}`}
        aria-label="Hide details flyout"
        onClick={onClose}
      />

      <aside
        className={`detail-flyout${isOpen ? " is-open" : ""}`}
        aria-label="Photo details flyout"
      >
        <div className="detail-flyout-header">
          <h2>{detail.photo_id}</h2>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="detail-path">{detail.path}</p>

        <article className="detail-panel">
          <h2>Summary</h2>
          <dl>
            <div>
              <dt>Captured</dt>
              <dd>{formatTimestamp(detail.shot_ts)}</dd>
            </div>
            <div>
              <dt>File size</dt>
              <dd>{formatFilesize(detail.filesize)}</dd>
            </div>
            <div>
              <dt>Camera make</dt>
              <dd>{formatOptionalText(detail.camera_make)}</dd>
            </div>
            <div>
              <dt>Orientation</dt>
              <dd>{formatOptionalText(detail.orientation)}</dd>
            </div>
            <div>
              <dt>Availability</dt>
              <dd>{detail.original?.availability_state ?? "Unknown availability"}</dd>
            </div>
            <div>
              <dt>Ingest status</dt>
              <dd>
                {ingestStatus ? (
                  <span className={`ingest-status-badge is-${ingestStatus.tone}`}>{ingestStatus.label}</span>
                ) : (
                  "Unknown"
                )}
              </dd>
            </div>
          </dl>
          {ingestStatus ? <p className="detail-ingest-status-detail">{ingestStatus.description}</p> : null}
        </article>

        <article className="detail-panel">
          <h2>Metadata</h2>
          <dl>
            <div>
              <dt>SHA-256</dt>
              <dd>{detail.metadata.sha256}</dd>
            </div>
            <div>
              <dt>Perceptual hash</dt>
              <dd>{formatOptionalText(detail.metadata.phash)}</dd>
            </div>
            <div>
              <dt>Timestamp source</dt>
              <dd>{formatOptionalText(detail.metadata.shot_ts_source)}</dd>
            </div>
            <div>
              <dt>Camera model</dt>
              <dd>{formatOptionalText(detail.metadata.camera_model)}</dd>
            </div>
            <div>
              <dt>Software</dt>
              <dd>{formatOptionalText(detail.metadata.software)}</dd>
            </div>
            <div>
              <dt>GPS</dt>
              <dd>{formatGps(detail.metadata.gps_latitude, detail.metadata.gps_longitude)}</dd>
            </div>
            <div>
              <dt>GPS altitude</dt>
              <dd>
                {detail.metadata.gps_altitude === null
                  ? MISSING_VALUE
                  : `${detail.metadata.gps_altitude.toFixed(1)} m`}
              </dd>
            </div>
            <div>
              <dt>Faces</dt>
              <dd>{facesLabel}</dd>
            </div>
            <div>
              <dt>Face detection run</dt>
              <dd>{formatTimestamp(detail.metadata.faces_detected_ts)}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatTimestamp(detail.metadata.created_ts)}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{formatTimestamp(detail.metadata.updated_ts)}</dd>
            </div>
            <div>
              <dt>Modified</dt>
              <dd>{formatTimestamp(detail.metadata.modified_ts)}</dd>
            </div>
          </dl>
          {exifAttributeEntries.length > 0 ? (
            <section className="detail-exif-attributes">
              <button
                type="button"
                className="detail-exif-attributes-toggle"
                aria-expanded={isExifAttributesOpen}
                aria-controls="detail-exif-attributes-list"
                onClick={() => setIsExifAttributesOpen((current) => !current)}
              >
                {isExifAttributesOpen ? "Hide all EXIF attributes" : "Show all EXIF attributes"}
              </button>
              {isExifAttributesOpen ? (
                <dl id="detail-exif-attributes-list" className="detail-exif-attributes-list">
                  {exifAttributeEntries.map(([attributeName, attributeValue]) => (
                    <div key={attributeName}>
                      <dt>{attributeName}</dt>
                      <dd>{formatExifAttributeValue(attributeValue)}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </section>
          ) : null}
        </article>

        <article className="detail-panel">
          <h2>Classification</h2>
          <dl>
            <div>
              <dt>Tags</dt>
              <dd>{detail.tags.length > 0 ? detail.tags.join(", ") : "No tags"}</dd>
            </div>
            <div>
              <dt>People</dt>
              <dd>{detail.people.length > 0 ? detail.people.join(", ") : "No recognized people"}</dd>
            </div>
          </dl>
        </article>
      </aside>
    </>
  );
}
