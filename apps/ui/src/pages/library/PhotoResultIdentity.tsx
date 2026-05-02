import type { ReactNode } from "react";

interface PhotoResultIdentityProps {
  title: ReactNode;
  path: string;
  pathClassName: string;
}

export function PhotoResultIdentity({ title, path, pathClassName }: PhotoResultIdentityProps) {
  return (
    <>
      <h2>{title}</h2>
      <p className={pathClassName} title={path}>
        {path}
      </p>
    </>
  );
}
