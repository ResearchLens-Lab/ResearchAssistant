"use client";

import React from "react";
import { useParams } from "next/navigation";
import { ThreePaneChatWorkbench } from "@/components/chat/ThreePaneChatWorkbench";

export default function ConversationChatPage() {
  const params = useParams();
  const conversationId = params.conversationId;

  return <ThreePaneChatWorkbench conversationId={conversationId} />;
}
