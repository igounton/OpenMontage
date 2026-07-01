import Link from "next/link";
import { Separator } from "@/components/ui/separator";

const NAV = [
  { href: "/dashboard", label: "Projects" },
  { href: "/dashboard/brands", label: "Brands" },
  { href: "/dashboard/settings", label: "Settings" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-border flex flex-col py-6 px-4 gap-6">
        <div className="px-2">
          <span className="text-lg font-bold tracking-tight text-foreground">OpenMontage</span>
          <p className="text-xs text-muted-foreground mt-0.5">AI Video Production Platform</p>
        </div>
        <Separator />
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
