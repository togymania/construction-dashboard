import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { UserProvider } from "@/components/providers/user-provider";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <UserProvider>
      {/* Premium ambient layers - fixed, behind everything */}
      <div className="mesh-gradient-bg" aria-hidden="true">
        <span className="mesh-blob" />
      </div>
      <div className="noise-overlay" aria-hidden="true" />

      {/* Main app shell */}
      <div className="relative z-10 flex min-h-screen">
        <Sidebar className="hidden lg:flex" />
        <div className="flex flex-1 flex-col">
          <Header />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>
    </UserProvider>
  );
}
