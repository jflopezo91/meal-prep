import { useState, useEffect } from 'react';
import { MealCard } from './components/MealCard';
import { ShoppingList } from './components/ShoppingList';
import { RecipeModal } from './components/RecipeModal';
import { Utensils, Calendar, Moon, Sun } from 'lucide-react';

// Map shorthand days to full names
const DAYS = {
  mon: 'Monday',
  tue: 'Tuesday',
  wed: 'Wednesday',
  thu: 'Thursday',
  fri: 'Friday',
  sat: 'Saturday',
  sun: 'Sunday'
};

const MEALS = ['lunch', 'dinner'];

function App() {
  const [plan, setPlan] = useState(null);
  const [shoppingList, setShoppingList] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Theme state
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined' && localStorage.getItem('theme')) {
      return localStorage.getItem('theme');
    }
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  });

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  useEffect(() => {
    async function fetchData() {
      try {
        const [planRes, shoppingRes] = await Promise.all([
          fetch(`./plan.json?t=${Date.now()}`),
          fetch(`./shopping_list.json?t=${Date.now()}`)
        ]);

        if (!planRes.ok || !shoppingRes.ok) {
          throw new Error('Failed to load data files');
        }

        const planData = await planRes.json();
        const shoppingData = await shoppingRes.json();

        setPlan(planData);
        setShoppingList(shoppingData);
      } catch (err) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="h-12 w-12 bg-slate-200 dark:bg-slate-800 rounded-full"></div>
          <div className="text-slate-400 font-medium">Loading Meal Plan...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-slate-900 p-8 rounded-xl shadow-lg border border-red-100 dark:border-red-900/30 max-w-md text-center">
          <div className="text-red-500 text-4xl mb-4">⚠️</div>
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100 mb-2">Error Loading Plan</h1>
          <p className="text-slate-600 dark:text-slate-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 px-6 py-2 bg-slate-900 dark:bg-slate-700 text-white rounded-lg hover:bg-slate-800 dark:hover:bg-slate-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Organize slots by day and meal
  const getSlot = (day, meal) => {
    return plan?.slots.find(s => s.day === day && s.meal === meal);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans pb-20 transition-colors duration-200">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-30 shadow-sm transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600 rounded-lg text-white">
              <Utensils size={20} />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-none text-slate-900 dark:text-white">Meal Prep</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Planner Iteration 3</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-xs text-slate-400 font-mono hidden sm:block">
              Seed: {plan.seed}
            </div>
            <button
              onClick={toggleTheme}
              className="p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">

          {/* Meal Grid (Takes up 3 columns on large screens) */}
          <div className="lg:col-span-3 space-y-8">
            <div className="flex items-center gap-2 mb-6">
              <Calendar className="text-indigo-600 dark:text-indigo-400" />
              <h2 className="text-xl font-bold text-slate-800 dark:text-white">Weekly Plan</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {Object.keys(DAYS).map(day => (
                <div key={day} className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col h-full transition-colors duration-200">
                  <div className="bg-slate-50 dark:bg-slate-800/50 px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                    <span className="font-bold text-slate-700 dark:text-slate-200">{DAYS[day]}</span>
                    <span className="text-xs text-slate-400 uppercase font-mono">{day}</span>
                  </div>

                  <div className="p-4 space-y-4 flex-1 flex flex-col justify-center">
                    {MEALS.map(meal => {
                      const slot = getSlot(day, meal);
                      if (!slot) return null;

                      return (
                        <MealCard
                          key={`${day}-${meal}`}
                          slot={slot}
                          onClick={() => setSelectedSlot(slot)}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {/* Stats Summary */}
            <div className="mt-12 bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 transition-colors duration-200">
              <h3 className="font-bold text-slate-800 dark:text-white mb-4">Distribution Stats</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                  <h4 className="text-xs uppercase text-slate-500 dark:text-slate-400 mb-2">Protein</h4>
                  <ul className="space-y-1 text-sm">
                    {Object.entries(plan.derived.protein_counts).map(([key, count]) => (
                      <li key={key} className="flex justify-between text-slate-700 dark:text-slate-300">
                        <span className="capitalize">{key}</span>
                        <span className="font-mono font-bold text-slate-900 dark:text-white">{count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="text-xs uppercase text-slate-500 dark:text-slate-400 mb-2">Carbs</h4>
                  <ul className="space-y-1 text-sm">
                    {Object.entries(plan.derived.carb_counts).map(([key, count]) => (
                      <li key={key} className="flex justify-between text-slate-700 dark:text-slate-300">
                        <span className="capitalize">{key}</span>
                        <span className="font-mono font-bold text-slate-900 dark:text-white">{count}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Shopping List Sidebar */}
          <div className="lg:col-span-1 h-fit sticky top-24">
            <ShoppingList items={shoppingList} />
          </div>
        </div>
      </main>

      {/* Recipe Modal */}
      {selectedSlot && (
        <RecipeModal
          slot={selectedSlot}
          onClose={() => setSelectedSlot(null)}
        />
      )}
    </div>
  );
}

export default App;
