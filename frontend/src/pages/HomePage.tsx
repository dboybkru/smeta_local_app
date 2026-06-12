import AppHeader from "../components/AppHeader";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8 text-stone-600">
        Каталог и импорт прайсов готовы. Откройте «Каталог» или «Импорт» в меню.
      </main>
    </div>
  );
}
