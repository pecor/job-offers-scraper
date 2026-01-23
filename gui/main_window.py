import logging
import threading

from typing import Any
from nicegui import ui
from config.config_manager import ConfigManager
from database.db_manager import DatabaseManager
from scrapers.pracuj_pl import PracujPlScraper

logger = logging.getLogger(__name__)


class MainWindow:
    def __init__(self):
        self.config = ConfigManager()
        self.db = DatabaseManager()
        self.selected_offers: set[int] = set()
        self.offers_data: list[dict[str, Any]] = []
        self.offers_container = None
        self.selected_technologies: set[str] = set()
        
        self._create_ui()

    def _create_ui(self) -> None:
        ui.page_title('Job offers scraper')
        
        with ui.header().classes('items-center justify-between bg-blue-500 text-white p-4'):
            with ui.row().classes('items-center gap-4'):
                ui.icon('settings', size='2rem').classes('cursor-pointer').on('click', self._open_config_modal)
                ui.label('Job offers scraper').classes('text-2xl font-bold')
        
        self._create_offers_panel()
        
        with ui.footer().classes('bg-gray-100 p-4 text-center text-sm text-gray-600 justify-center'):
            with ui.row().classes('justify-center items-center gap-2'):
                ui.label('Created by').classes('text-gray-600')
                ui.link('pecor', 'https://github.com/pecor', new_tab=True).classes('text-blue-600 hover:text-blue-800')
                ui.label('•').classes('text-gray-400')
                ui.link('GitHub Repository', 'https://github.com/pecor/job-offers-scraper', new_tab=True).classes('text-blue-600 hover:text-blue-800')

    def _open_config_modal(self) -> None:
        with ui.dialog() as config_dialog, ui.card().classes('w-full max-w-2xl p-6 gap-4'):
            ui.label('Scraper configuration').classes('text-xl font-bold')
            
            keyword_input = ui.input(
                'Search keyword',
                value=self.config.get('search_keyword', 'junior')
            ).classes('w-full')
            
            max_pages_input = ui.number(
                'Max pages',
                value=self.config.get('max_pages', 5),
                min=1,
                max=100
            ).classes('w-full')
            
            delay_input = ui.number(
                'Delay (seconds)',
                value=self.config.get('delay', 1.0),
                min=0.1,
                max=10.0,
                step=0.1
            ).classes('w-full')
            
            domain_select = ui.select(
                {'it': 'IT (it.pracuj.pl)', 'www': 'All (www.pracuj.pl)'},
                label='Pracuj.pl Domain',
                value=self.config.get('pracuj_pl_domain', 'it')
            ).classes('w-full')
            
            ui.label('Excluded keywords (one per line)')
            excluded_keywords_textarea = ui.textarea(
                value='\n'.join(self.config.get('excluded_keywords', []))
            ).classes('w-full').style('min-height: 100px')
            
            schedule_select = ui.select(
                ['daily', 'weekly', 'manual'],
                label='Schedule',
                value=self.config.get('schedule', 'daily')
            ).classes('w-full')
            
            def save_config():
                try:
                    excluded_keywords = [
                        line.strip() for line in excluded_keywords_textarea.value.split('\n')
                        if line.strip()
                    ]
                    
                    self.config.update({
                        'search_keyword': keyword_input.value,
                        'max_pages': int(max_pages_input.value),
                        'delay': float(delay_input.value),
                        'pracuj_pl_domain': domain_select.value,
                        'excluded_keywords': excluded_keywords,
                        'schedule': schedule_select.value,
                    })
                    self.config.save_config()
                    ui.notify('Configuration saved!', type='positive')
                    config_dialog.close()
                except Exception as e:
                    ui.notify(f'Error saving configuration: {e}', type='negative')
            
            with ui.row().classes('w-full gap-2'):
                ui.button('Save', on_click=save_config, icon='save').classes('flex-1 bg-blue-500 text-white')
                ui.button('Cancel', on_click=config_dialog.close).classes('flex-1')
            
            ui.separator()
            
            def run_scraper():
                try:
                    save_config()
                    
                    keyword = keyword_input.value
                    max_pages = int(max_pages_input.value)
                    delay = float(delay_input.value)
                    domain = domain_select.value
                    excluded = excluded_keywords_textarea.value.split('\n')
                    
                    self.config.update({
                        'search_keyword': keyword,
                        'max_pages': max_pages,
                        'delay': delay,
                        'pracuj_pl_domain': domain,
                        'excluded_keywords': [e.strip() for e in excluded if e.strip()],
                    })
                    self.config.save_config()
                    
                    def run_scraper_thread():
                        try:
                            scraper = PracujPlScraper({
                                'delay': delay,
                                'pracuj_pl_domain': domain
                            })
                            excluded_keywords = [e.strip() for e in excluded if e.strip()]
                            
                            if hasattr(scraper, 'scrape_page_by_page'):
                                saved_count = scraper.scrape_page_by_page(keyword, max_pages, self.db, excluded_keywords)
                                ui.notify(f'Scraping completed! Saved: {saved_count} new offers', type='positive')
                            else:
                                ui.notify('Scraper method not available', type='negative')
                        except Exception as e:
                            ui.notify(f'Error during scraping: {e}', type='negative')
                            logger.error(f"Error during scraping: {e}", exc_info=True)
                        finally:
                            self._refresh_offers_list()
                    
                    thread = threading.Thread(target=run_scraper_thread, daemon=True)
                    thread.start()
                    
                    ui.notify('Scraper started! This may take a while...', type='info')
                    logger.info("Started scraper in background thread")
                    config_dialog.close()
                except Exception as e:
                    ui.notify(f'Error starting scraper: {e}', type='negative')
                    logger.error(f"Error starting scraper: {e}", exc_info=True)
            
            ui.button('Run Scraper', on_click=run_scraper, icon='play_arrow').classes('w-full bg-green-500 text-white')
        
        config_dialog.open()

    def _open_tech_filter_modal(self) -> None:
        offers = self.db.get_offers(limit=10000)
        all_techs = set()
        for offer in offers:
            if offer.get('technologies'):
                techs = [t.strip() for t in offer.get('technologies', '').split(',') if t.strip()]
                all_techs.update(techs)
        
        sorted_techs = sorted(all_techs)
        
        with ui.dialog() as tech_dialog, ui.card().classes('w-full max-w-3xl p-6 gap-4'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Filter by technologies').classes('text-xl font-bold')
                search_input = ui.input('', placeholder='Search technologies (e.g. "react")').classes('flex-1 max-w-xs').style('color: #666;')
                ui.add_head_html('''
                    <style>
                        input::placeholder {
                            color: #999 !important;
                            opacity: 1 !important;
                        }
                    </style>
                ''')
            
            with ui.scroll_area().classes('w-full h-[400px]'):
                tech_container = ui.column().classes('w-full gap-2')
            
            def filter_techs():
                search_term = search_input.value.lower() if search_input.value else ''
                tech_container.clear()
                
                filtered_techs = [t for t in sorted_techs if search_term in t.lower()] if search_term else sorted_techs
                
                for tech in filtered_techs:
                    is_selected = tech in self.selected_technologies
                    with tech_container:
                        def toggle_tech(tech_name=tech):
                            if tech_name in self.selected_technologies:
                                self.selected_technologies.discard(tech_name)
                            else:
                                self.selected_technologies.add(tech_name)
                            filter_techs()
                        
                        with ui.row().classes('w-full items-center gap-2 p-2').style('cursor: pointer; border: 1px solid #ddd; border-radius: 4px;').on('click', lambda t=tech: toggle_tech(t)):
                            checkbox = ui.checkbox('', value=is_selected).classes('flex-shrink-0')
                            checkbox.on('click', lambda e: e.stop_propagation())
                            checkbox.on_value_change(lambda e, t=tech: toggle_tech(t))
                            
                            ui.label(tech).classes('flex-grow')
                            
                            if is_selected:
                                ui.icon('check', color='blue').classes('flex-shrink-0')
            
            search_input.on_value_change(lambda: filter_techs())
            
            with ui.row().classes('w-full gap-2'):
                def select_all_visible():
                    search_term = search_input.value.lower()
                    filtered_techs = [t for t in sorted_techs if search_term in t.lower()]
                    for tech in filtered_techs:
                        self.selected_technologies.add(tech)
                    filter_techs()
                
                def deselect_all_visible():
                    search_term = search_input.value.lower()
                    filtered_techs = [t for t in sorted_techs if search_term in t.lower()]
                    for tech in filtered_techs:
                        self.selected_technologies.discard(tech)
                    filter_techs()
                
                ui.button('Select All', on_click=select_all_visible, icon='check_box').classes('text-xs')
                ui.button('Deselect All', on_click=deselect_all_visible, icon='check_box_outline_blank').classes('text-xs')
            
            filter_techs()
            
            with ui.row().classes('w-full gap-2'):
                def apply_filter():
                    self._refresh_offers_list()
                    tech_dialog.close()
                
                def clear_filter():
                    self.selected_technologies.clear()
                    self._refresh_offers_list()
                    tech_dialog.close()
                
                ui.button('Apply', on_click=apply_filter, icon='check').classes('flex-1 bg-blue-500 text-white')
                ui.button('Clear', on_click=clear_filter).classes('flex-1')
                ui.button('Cancel', on_click=tech_dialog.close).classes('flex-1')
        
        tech_dialog.open()

    def _create_offers_panel(self) -> None:
        with ui.column().classes('w-full gap-4 p-4'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Job offers').classes('text-xl font-bold')
                
                with ui.row().classes('gap-2'):
                    def select_all():
                        for offer in self.offers_data:
                            self.selected_offers.add(offer['id'])
                        self._refresh_offers_list()
                    
                    def deselect_all():
                        all_offers = self.db.get_offers(limit=10000)
                        for offer in all_offers:
                            self.selected_offers.discard(offer.get('id'))
                        self._refresh_offers_list()
                    
                    def open_selected():
                        if not self.selected_offers:
                            ui.notify('No offers selected', type='warning')
                            return
                        
                        selected_urls = [
                            offer['url'] for offer in self.offers_data
                            if offer['id'] in self.selected_offers
                        ]
                        
                        for url in selected_urls:
                            ui.open(url, new_tab=True)
                        
                        ui.notify(f'Opened {len(selected_urls)} offers in new tabs', type='info')
                    
                    ui.button('Filter', on_click=self._open_tech_filter_modal, icon='filter_list').classes('bg-purple-500 text-white')
                    if self.selected_technologies:
                        ui.badge(str(len(self.selected_technologies)), color='purple').classes('ml-[-8px]')
                    
                    ui.button('Select All', on_click=select_all, icon='check_box')
                    ui.button('Deselect All', on_click=deselect_all, icon='check_box_outline_blank')
                    ui.button('Open Selected', on_click=open_selected, icon='open_in_new').classes('bg-green-500 text-white')
                    ui.button('Refresh', on_click=self._refresh_offers_list, icon='refresh')
            
            ui.add_head_html('''
                <style>
                    .hide-scrollbar::-webkit-scrollbar {
                        display: none;
                    }
                    .hide-scrollbar {
                        -ms-overflow-style: none;
                        scrollbar-width: none;
                    }
                </style>
            ''')
            with ui.scroll_area().classes('w-full hide-scrollbar').style('height: calc(100vh - 200px); overflow-y: auto;'):
                self.offers_container = ui.column().classes('w-full gap-2')
            
            self._refresh_offers_list()

    def _refresh_offers_list(self) -> None:
        if self.offers_container is None:
            return
        
        self.offers_container.clear()
        
        offers = self.db.get_offers(limit=500)
        
        if self.selected_technologies:
            filtered_offers = []
            for offer in offers:
                if offer.get('technologies'):
                    offer_techs = [t.strip().lower() for t in offer.get('technologies', '').split(',') if t.strip()]
                    selected_techs_lower = {t.lower() for t in self.selected_technologies}
                    if any(tech in selected_techs_lower for tech in offer_techs):
                        filtered_offers.append(offer)
            offers = filtered_offers
        
        self.offers_data = offers
        
        if not offers:
            with self.offers_container:
                ui.label('No offers found').classes('text-gray-500 p-4')
            return
        
        for offer in offers:
            offer_id = offer.get('id')
            is_selected = offer_id in self.selected_offers
            
            with self.offers_container:
                card_ref = [None]
                checkbox_ref = [None]
                
                def create_toggle_handler(oid, cr, chr):
                    def toggle_selection():
                        if oid in self.selected_offers:
                            self.selected_offers.remove(oid)
                            new_bg = 'white'
                            new_value = False
                        else:
                            self.selected_offers.add(oid)
                            new_bg = '#e3f2fd'
                            new_value = True
                        
                        if cr[0]:
                            cr[0].style(f'cursor: pointer; background-color: {new_bg};')
                            cr[0].update()
                        if chr[0]:
                            chr[0].value = new_value
                            chr[0].update()
                    return toggle_selection
                
                def create_checkbox_handler(oid, cr):
                    def on_checkbox_change(e):
                        value = e.value if hasattr(e, 'value') else e
                        if value:
                            self.selected_offers.add(oid)
                            new_bg = '#e3f2fd'
                        else:
                            self.selected_offers.discard(oid)
                            new_bg = 'white'
                        
                        if cr[0]:
                            cr[0].style(f'cursor: pointer; background-color: {new_bg};')
                            cr[0].update()
                    return on_checkbox_change
                
                _ = create_toggle_handler(offer_id, card_ref, checkbox_ref)
                on_checkbox_change = create_checkbox_handler(offer_id, card_ref)
                
                bg_color = '#e3f2fd' if is_selected else 'white'
                with ui.card().classes('w-full p-4').style(f'cursor: pointer; background-color: {bg_color};') as card:
                    card_ref[0] = card
                    
                    def card_click_handler(e, oid=offer_id, cr=card_ref, chr=checkbox_ref):
                        if oid in self.selected_offers:
                            self.selected_offers.remove(oid)
                            new_bg = 'white'
                            new_value = False
                        else:
                            self.selected_offers.add(oid)
                            new_bg = '#e3f2fd'
                            new_value = True
                        
                        if cr[0]:
                            cr[0].style(f'cursor: pointer; background-color: {new_bg};')
                            cr[0].update()
                        if chr[0]:
                            chr[0].value = new_value
                            chr[0].update()
                    
                    card.on('click', card_click_handler)
                    
                    with ui.row().classes('w-full items-center gap-4'):
                        def on_checkbox_click(e):
                            e.stop_propagation()
                        
                        checkbox = ui.checkbox('', value=is_selected).classes('flex-shrink-0')
                        checkbox_ref[0] = checkbox
                        checkbox.on('click', on_checkbox_click)
                        checkbox.on_value_change(on_checkbox_change)
                        
                        with ui.column().classes('flex-grow gap-1'):
                            title = offer.get('title', 'No title')
                            company = offer.get('company', 'Unknown')
                            location = offer.get('location', '')
                            
                            ui.label(title).classes('text-lg font-semibold')
                            
                            with ui.row().classes('gap-4 text-sm text-gray-600'):
                                ui.label(f'Company: {company}')
                                if location:
                                    ui.label(f'Location: {location}')
                            
                            with ui.row().classes('gap-4 text-sm'):
                                salary_str = ""
                                if offer.get('salary_min'):
                                    if offer.get('salary_max') and offer.get('salary_max') != offer.get('salary_min'):
                                        salary_str = f"{offer.get('salary_min')} - {offer.get('salary_max')}"
                                    else:
                                        salary_str = str(offer.get('salary_min'))
                                    if offer.get('salary_period'):
                                        salary_str += f" /{offer.get('salary_period')}"
                                
                                if salary_str:
                                    ui.label(f'Salary: {salary_str}').classes('text-green-600 font-medium')
                                
                                if offer.get('work_type'):
                                    ui.label(f'Work: {offer.get("work_type")}').classes('text-blue-600')
                                
                                if offer.get('contract_type'):
                                    ui.label(f'Contract: {offer.get("contract_type")}').classes('text-purple-600')
                            
                            if offer.get('technologies'):
                                techs = offer.get('technologies', '').split(', ')
                                techs_display = ', '.join(techs[:10])
                                if len(techs) > 10:
                                    techs_display += f' (+{len(techs) - 10} more)'
                                ui.label(f'Tech: {techs_display}').classes('text-sm text-orange-600')
                            
                            with ui.row().classes('gap-4 text-xs text-gray-500'):
                                if offer.get('scraped_at'):
                                    date_str = str(offer.get('scraped_at'))[:10]
                                    ui.label(f'Scraped: {date_str}')
                                
                                if offer.get('valid_until'):
                                    valid_until_str = str(offer.get('valid_until'))
                                    ui.label(f'Valid until: {valid_until_str}').classes('text-red-600 font-medium')
                        
                        with ui.row().classes('gap-2 flex-shrink-0'):
                            def open_link(e, url=offer.get('url', '')):
                                e.stop_propagation()
                                ui.open(url, new_tab=True)
                            
                            open_btn = ui.button('Open', icon='open_in_new').classes('bg-blue-500 text-white')
                            open_btn.on('click', lambda e, u=offer.get('url', ''): open_link(e, u))
        
