from django.urls import path

from . import (
    ai_views,
    ask_views,
    budget,
    categories,
    imports,
    insights_page,
    transactions,
    trends,
    views,
    wealth,
)

app_name = "web"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("transactions/", transactions.transactions, name="transactions"),
    path("trends/", trends.trends, name="trends"),
    path("insights/", insights_page.insights, name="insights"),
    path("years/", wealth.years, name="years"),
    path("years/new/", wealth.year_edit, name="year_new"),
    path("years/<int:year>/edit/", wealth.year_edit, name="year_edit"),
    path("debt/", wealth.debt, name="debt"),
    path("ai/<slug:card>/", ai_views.ask, name="ai_ask"),
    path("ask/", ask_views.ask_page, name="ask"),
    path("budget/", budget.budget, name="budget"),
    path("budget/create/", budget.budget_create, name="budget_create"),
    path("budget/save/", budget.budget_save, name="budget_save"),
    path("budget/goals/add/", budget.goal_add, name="goal_add"),
    path("budget/goals/<int:pk>/delete/", budget.goal_delete, name="goal_delete"),
    path("debt/add/", wealth.debt_add, name="debt_add"),
    path("debt/<int:pk>/delete/", wealth.debt_delete, name="debt_delete"),
    path("categories/", categories.categories, name="categories"),
    path("categories/assign/", categories.assign, name="assign"),
    path("import/", imports.import_page, name="import"),
    path("import/confirm/", imports.import_confirm, name="import_confirm"),
    path("import/<int:pk>/undo/", imports.import_undo, name="import_undo"),
]
