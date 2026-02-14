import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { Check, ShoppingCart } from 'lucide-react';

export function ShoppingList({ items }) {
    const [checkedItems, setCheckedItems] = useState(() => {
        const saved = localStorage.getItem('shopping_checked');
        return saved ? JSON.parse(saved) : {};
    });

    useEffect(() => {
        localStorage.setItem('shopping_checked', JSON.stringify(checkedItems));
    }, [checkedItems]);

    const toggleItem = (itemKey) => {
        setCheckedItems(prev => ({
            ...prev,
            [itemKey]: !prev[itemKey]
        }));
    };

    // If undefined or loading
    if (!items || !items.sections) return <div className="p-4 text-slate-500">Loading list...</div>;

    // Transform the sections object into an array for rendering
    const categories = Object.entries(items.sections).map(([section, sectionItems]) => ({
        category: section,
        items: sectionItems
    }));

    // Calculate total items count
    const totalItemsCount = categories.flatMap(c => c.items).length;

    return (
        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-gray-200 dark:border-slate-800 overflow-hidden h-full flex flex-col transition-colors duration-200">
            <div className="bg-slate-900 dark:bg-slate-950 text-white p-4 flex items-center justify-between sticky top-0 z-10">
                <h2 className="text-lg font-bold flex items-center gap-2">
                    <ShoppingCart size={20} />
                    Shopping List
                </h2>
                <span className="text-xs bg-slate-700 dark:bg-slate-800 px-2 py-1 rounded-full">
                    {Object.values(checkedItems).filter(Boolean).length} / {totalItemsCount}
                </span>
            </div>

            <div className="divide-y divide-gray-100 dark:divide-slate-800 flex-1 overflow-y-auto bg-white dark:bg-slate-900">
                {categories.map((category) => (
                    <div key={category.category} className="p-4">
                        <h3 className="font-semibold text-slate-800 dark:text-slate-200 mb-3 uppercase text-xs tracking-wider sticky top-0 bg-white dark:bg-slate-900 py-1">
                            {category.category}
                        </h3>
                        <ul className="space-y-2">
                            {category.items.map((item) => {
                                const itemKey = item.item; // Use stable ID
                                return (
                                    <li
                                        key={itemKey}
                                        className={cn(
                                            "flex items-start gap-3 p-2 rounded-lg transition-colors cursor-pointer select-none",
                                            checkedItems[itemKey] ? "bg-slate-50 dark:bg-slate-800 opacity-50" : "hover:bg-slate-50 dark:hover:bg-slate-800"
                                        )}
                                        onClick={() => toggleItem(itemKey)}
                                    >
                                        <div className={cn(
                                            "mt-0.5 w-5 h-5 rounded border border-slate-300 dark:border-slate-600 flex items-center justify-center shrink-0 transition-colors",
                                            checkedItems[itemKey] ? "bg-green-500 border-green-500 text-white" : "bg-white dark:bg-slate-800"
                                        )}>
                                            {checkedItems[itemKey] && <Check size={14} strokeWidth={3} />}
                                        </div>
                                        <div className="flex-1">
                                            <span className={cn(
                                                "text-sm font-medium block text-slate-900 dark:text-slate-200",
                                                checkedItems[itemKey] && "line-through text-slate-500 dark:text-slate-500"
                                            )}>
                                                {item.display}
                                            </span>
                                            <span className="text-xs text-slate-500 dark:text-slate-400">
                                                {item.quantity} {item.unit}
                                            </span>
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    </div>
                ))}
            </div>
        </div>
    );
}
