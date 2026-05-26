"""
survey/urls.py
"""
from django.urls import path
from . import views

app_name = 'survey'

urlpatterns = [
    # Overview — all routes
    path('', views.overview, name='overview'),

    # Route detail — map + tables
    path('route/<str:route_id>/', views.route_detail, name='route_detail'),

    # Printable report
    path('route/<str:route_id>/report/', views.route_report, name='route_report'),

    # Summary charts
    path('route/<str:route_id>/summary/', views.route_summary, name='route_summary'),

    # Report Excel export
    path('route/<str:route_id>/report/excel/', views.route_report_excel, name='route_report_excel'),

    # Photo library and downloads
    path('downloads/', views.photo_library, name='photo_library'),
]
