"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/lib/api";

export function useWebSocket() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    // Use current host or NEXT_PUBLIC_API_URL
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsProto = apiUrl.startsWith("https") ? "wss" : "ws";
    const host = apiUrl.replace(/^https?:\/\//, "");
    const wsUrl = `${wsProto}://${host}/api/v1/ws?token=${token}`;

    let socket: WebSocket;
    let pingInterval: any;

    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        // Heartbeat ping every 25 seconds
        pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 25000);
      };

      socket.onmessage = (event) => {
        if (event.data === "pong") return;
        try {
          const payload = JSON.parse(event.data);
          const { event: eventName } = payload;

          if (eventName === "notification_received") {
            queryClient.invalidateQueries({ queryKey: ["notifications"] });
          } else if (eventName === "task_updated" || eventName === "task_created") {
            queryClient.invalidateQueries({ queryKey: ["tasks"] });
          } else if (eventName === "project_updated") {
            queryClient.invalidateQueries({ queryKey: ["projects"] });
          }
        } catch (e) {
          // Ignore parsing errors for raw text
        }
      };

      socket.onclose = () => {
        clearInterval(pingInterval);
      };
    } catch (err) {
      console.warn("WebSocket connection skipped or unavailable:", err);
    }

    return () => {
      clearInterval(pingInterval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [queryClient]);
}
