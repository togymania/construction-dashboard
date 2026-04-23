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
      <div className="flex min-h-screen">
        <Sidebar className="hidden lg:flex" />
        <div className="flex flex-1 flex-col">
          <Header />
          <main className="flex-1 p-6 bg-muted/20">{children}</main>
        </div>
      </div>
    </UserProvider>
  );
}
