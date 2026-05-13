import Link from "next/link";

/**
 * Monotekstroy marka logosu — auth ekranında merkezi başlık olarak
 * kullanılır. İki üst üste binmiş chevron (ev çatısı) şekli, kendi
 * resmî renkleriyle (koyu lacivert + açık mavi).
 */
function MonotekstroyMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <polygon points="50,12 95,50 76,50 50,28 24,50 5,50" fill="#143C73" />
      <polygon points="50,48 95,90 5,90" fill="#1FA3DA" />
    </svg>
  );
}

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-muted/20 p-4">
      <Link href="/" className="flex items-center gap-3 mb-8">
        <MonotekstroyMark className="h-10 w-10" />
        <span className="text-2xl font-extrabold tracking-tight">
          <span className="text-[#143C73] dark:text-slate-100">MONOTEK</span>
          <span className="text-[#1FA3DA]">STROY</span>
        </span>
      </Link>
      <div className="w-full max-w-md">{children}</div>
      <p className="mt-8 text-xs text-muted-foreground">
        AI Destekli İnşaat Proje Yönetimi
      </p>
    </div>
  );
}
