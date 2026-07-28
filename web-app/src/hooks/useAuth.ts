import { FormEvent, useCallback, useEffect, useState } from "react";

import { apiRequest, AUTH_INVALID_EVENT } from "../api/client";

type UseAuthOptions = {
  onError: (message: string) => void;
};

export function useAuth({ onError }: UseAuthOptions) {
  const [token, setToken] = useState<string>(() => localStorage.getItem("tb_token") ?? "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const signOut = useCallback(() => {
    setToken("");
    localStorage.removeItem("tb_token");
  }, []);

  useEffect(() => {
    const handleInvalidSession = () => {
      signOut();
      onError("Your session expired or is no longer valid. Please sign in again.");
    };
    window.addEventListener(AUTH_INVALID_EVENT, handleInvalidSession);
    return () => window.removeEventListener(AUTH_INVALID_EVENT, handleInvalidSession);
  }, [onError, signOut]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await apiRequest<{ access_token: string }>("/api/auth/login", "POST", { username, password });
      setToken(response.access_token);
      localStorage.setItem("tb_token", response.access_token);
      onError("");
    } catch (err) {
      onError((err as Error).message);
    }
  }

  return {
    token,
    username,
    password,
    setUsername,
    setPassword,
    setToken,
    handleLogin,
    signOut,
  };
}
