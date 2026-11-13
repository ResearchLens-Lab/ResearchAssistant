import React from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";

export default function PdfLayout({ children }) {
  return <AuthGuard>{children}</AuthGuard>;
}
