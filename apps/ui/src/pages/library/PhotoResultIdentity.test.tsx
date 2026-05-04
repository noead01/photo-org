import { render, screen } from "@testing-library/react";
import { PhotoResultIdentity } from "./PhotoResultIdentity";

describe("PhotoResultIdentity", () => {
  it("renders title content and path text with tooltip", () => {
    render(
      <PhotoResultIdentity
        title={<span>photo-123</span>}
        path="/storage-sources/source-a/folder/image_9999.jpg"
        pathClassName="browse-path"
      />
    );

    expect(screen.getByRole("heading", { name: "photo-123" })).toBeInTheDocument();
    const pathElement = screen.getByText("/storage-sources/source-a/folder/image_9999.jpg");
    expect(pathElement).toHaveClass("browse-path");
    expect(pathElement).toHaveAttribute(
      "title",
      "/storage-sources/source-a/folder/image_9999.jpg"
    );
  });
});
