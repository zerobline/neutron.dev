import { Header } from "@/components/layout/header";
import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-12">
        <LoginForm />
      </main>
    </div>
  );
}
