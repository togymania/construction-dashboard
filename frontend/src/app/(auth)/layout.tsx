import Link from "next/link";
import Image from "next/image";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-muted/20 p-4">
      <Link href="/" className="flex items-center mb-8" aria-label="Monotekstroy">
        <Image
          src="/monotekstroy-logo.png"
          alt="Monotekstroy"
          width={280}
          height={64}
          priority
          className="h-12 w-auto"
        />
      </Link>
      <div className="w-full max-w-md">{children}</div>
      <p className="mt-8 text-xs text-muted-foreground">
        AI Destekli İnşaat Proje Yönetimi
      </p>
    </div>
  );
}
