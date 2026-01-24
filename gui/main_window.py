import logging
import threading
from datetime import datetime, date

from typing import Any
from nicegui import ui
from config.config_manager import ConfigManager
from database.db_manager import DatabaseManager
from scrapers.pracuj_pl import PracujPlScraper
from scrapers.justjoin_it import JustJoinItScraper

logger = logging.getLogger(__name__)


class MainWindow:
    def __init__(self):
        self.config = ConfigManager()
        self.db = DatabaseManager()
        self.selected_offers: set[int] = set()
        self.offers_data: list[dict[str, Any]] = []
        self.offers_container = None
        self.selected_technologies: set[str] = set()
        self.required_keywords_filter: set[str] = set()
        self.excluded_keywords_filter: set[str] = set()
        self.offers_count_label = None
        self.sort_by: str = 'scraped_at'
        self.sort_order: str = 'desc'
        
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
            
            ui.label('Sources (select multiple)').classes('text-sm font-semibold')
            sources_config = self.config.get('sources', ['pracuj_pl'])
            pracuj_pl_checkbox = ui.checkbox('Pracuj.pl', value='pracuj_pl' in sources_config).classes('w-full')
            justjoin_it_checkbox = ui.checkbox('JustJoin.it', value='justjoin_it' in sources_config).classes('w-full')
            
            def save_config():
                try:
                    excluded_keywords = [
                        line.strip() for line in excluded_keywords_textarea.value.split('\n')
                        if line.strip()
                    ]
                    
                    selected_sources = []
                    if pracuj_pl_checkbox.value:
                        selected_sources.append('pracuj_pl')
                    if justjoin_it_checkbox.value:
                        selected_sources.append('justjoin_it')
                    
                    if not selected_sources:
                        ui.notify('Please select at least one source', type='warning')
                        return
                    
                    self.config.update({
                        'search_keyword': keyword_input.value,
                        'max_pages': int(max_pages_input.value),
                        'delay': float(delay_input.value),
                        'pracuj_pl_domain': domain_select.value,
                        'excluded_keywords': excluded_keywords,
                        'schedule': schedule_select.value,
                        'sources': selected_sources,
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
                    
                    selected_sources = []
                    if pracuj_pl_checkbox.value:
                        selected_sources.append('pracuj_pl')
                    if justjoin_it_checkbox.value:
                        selected_sources.append('justjoin_it')
                    
                    if not selected_sources:
                        ui.notify('Please select at least one source', type='warning')
                        return
                    
                    self.config.update({
                        'search_keyword': keyword,
                        'max_pages': max_pages,
                        'delay': delay,
                        'pracuj_pl_domain': domain,
                        'sources': selected_sources,
                        'excluded_keywords': [e.strip() for e in excluded if e.strip()],
                    })
                    self.config.save_config()
                    
                    excluded_keywords = [e.strip() for e in excluded if e.strip()]
                    
                    def run_scraper_for_source(source_name: str):
                        """Run scraper for a specific source"""
                        try:
                            if source_name == 'pracuj_pl':
                                scraper = PracujPlScraper({
                                    'delay': delay,
                                    'pracuj_pl_domain': domain
                                })
                            elif source_name == 'justjoin_it':
                                scraper = JustJoinItScraper({
                                    'delay': delay
                                })
                            else:
                                logger.error(f'Unknown source: {source_name}')
                                return
                            
                            if hasattr(scraper, 'scrape_page_by_page'):
                                saved_count = scraper.scrape_page_by_page(keyword, max_pages, self.db, excluded_keywords)
                                ui.notify(f'{source_name} completed! Saved: {saved_count} new offers', type='positive')
                            else:
                                ui.notify(f'{source_name}: Scraper method not available', type='negative')
                        except Exception as e:
                            ui.notify(f'Error during scraping {source_name}: {e}', type='negative')
                            logger.error(f"Error during scraping {source_name}: {e}", exc_info=True)
                        finally:
                            self._refresh_offers_list()
                    
                    # Start a thread for each selected source
                    threads = []
                    for source in selected_sources:
                        thread = threading.Thread(target=run_scraper_for_source, args=(source,), daemon=True)
                        thread.start()
                        threads.append(thread)
                        logger.info(f"Started scraper thread for {source}")
                    
                    ui.notify(f'Started {len(selected_sources)} scraper(s)! This may take a while...', type='info')
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

    def _open_keywords_filter_modal(self) -> None:
        """Open modal to filter offers by keywords - required and excluded"""
        with ui.dialog() as keywords_dialog, ui.card().classes('w-full max-w-2xl p-6 gap-4'):
            ui.label('Filter by keywords').classes('text-xl font-bold')
            
            ui.label('Required keywords (comma-separated)').classes('text-sm font-semibold')
            ui.label('Offers must contain at least one of these keywords').classes('text-xs text-gray-600 mb-2')
            required_input = ui.textarea(
                value=', '.join(self.required_keywords_filter),
                placeholder='e.g. python, java, react'
            ).classes('w-full').style('min-height: 80px')
            
            ui.label('Excluded keywords (comma-separated)').classes('text-sm font-semibold mt-4')
            ui.label('Offers containing any of these keywords will be excluded').classes('text-xs text-gray-600 mb-2')
            excluded_input = ui.textarea(
                value=', '.join(self.excluded_keywords_filter),
                placeholder='e.g. consultant, administrator'
            ).classes('w-full').style('min-height: 80px')
            
            with ui.row().classes('w-full gap-2'):
                def apply_filter():
                    # Parse required keywords
                    required_text = required_input.value.strip()
                    if required_text:
                        self.required_keywords_filter = {kw.strip().lower() for kw in required_text.split(',') if kw.strip()}
                    else:
                        self.required_keywords_filter = set()
                    
                    # Parse excluded keywords
                    excluded_text = excluded_input.value.strip()
                    if excluded_text:
                        self.excluded_keywords_filter = {kw.strip().lower() for kw in excluded_text.split(',') if kw.strip()}
                    else:
                        self.excluded_keywords_filter = set()
                    
                    self._refresh_offers_list()
                    keywords_dialog.close()
                
                def clear_filter():
                    self.required_keywords_filter = set()
                    self.excluded_keywords_filter = set()
                    required_input.value = ''
                    excluded_input.value = ''
                    self._refresh_offers_list()
                    keywords_dialog.close()
                
                ui.button('Apply', on_click=apply_filter, icon='check').classes('flex-1 bg-orange-500 text-white')
                ui.button('Clear', on_click=clear_filter).classes('flex-1')
                ui.button('Cancel', on_click=keywords_dialog.close).classes('flex-1')
        
        keywords_dialog.open()

    def _create_offers_panel(self) -> None:
        with ui.column().classes('w-full gap-4 p-4'):
            with ui.row().classes('w-full items-center justify-between'):
                with ui.row().classes('items-center gap-2'):
                    ui.label('Job offers').classes('text-xl font-bold')
                    self.offers_count_label = ui.label('(selected 0/0)').classes('text-sm text-gray-600')
                
                with ui.row().classes('gap-2'):
                    def select_all():
                        for offer in self.offers_data:
                            self.selected_offers.add(offer['id'])
                        self._refresh_offers_list()
                    
                    def deselect_all():
                        all_offers = self.db.get_offers(limit=10000)
                        for offer in all_offers:
                            self.selected_offers.discard(offer.get('id'))

                        if self.offers_count_label:
                            total_count = len(self.offers_data)
                            self.offers_count_label.text = f'(selected 0/{total_count})'
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
                    
                    ui.button('Tech Filter', on_click=self._open_tech_filter_modal, icon='filter_list').classes('bg-purple-500 text-white')
                    if self.selected_technologies:
                        ui.badge(str(len(self.selected_technologies)), color='purple').classes('ml-[-8px]')
                    
                    ui.button('Keywords Filter', on_click=self._open_keywords_filter_modal, icon='filter_alt').classes('bg-orange-500 text-white')
                    filter_count = len(self.required_keywords_filter) + len(self.excluded_keywords_filter)
                    if filter_count > 0:
                        ui.badge(str(filter_count), color='orange').classes('ml-[-8px]')
                    
                    def open_sort_modal():
                        with ui.dialog() as sort_dialog, ui.card().classes('w-full max-w-md p-6 gap-4'):
                            ui.label('Sort by').classes('text-xl font-bold')
                            
                            sort_options = [
                                ('scraped_at', 'Scraped Date'),
                                ('valid_until', 'Valid Until'),
                                ('title', 'Title'),
                                ('company', 'Company')
                            ]
                            
                            for sort_key, sort_label in sort_options:
                                def create_sort_handler(key=sort_key):
                                    def on_sort_click():
                                        if self.sort_by == key:
                                            self.sort_order = 'asc' if self.sort_order == 'desc' else 'desc'
                                        else:
                                            self.sort_by = key
                                            self.sort_order = 'desc'
                                        self._refresh_offers_list()
                                        sort_dialog.close()
                                    return on_sort_click
                                
                                is_selected = self.sort_by == sort_key
                                sort_icon = ' (ASC)' if (is_selected and self.sort_order == 'asc') else (' (DESC)' if is_selected else '')
                                
                                with ui.row().classes('w-full items-center gap-2 p-2').style('cursor: pointer; border: 1px solid #ddd; border-radius: 4px;').on('click', create_sort_handler(sort_key)):
                                    ui.label(f'{sort_label}{sort_icon}').classes('flex-grow')
                                    if is_selected:
                                        ui.icon('check', color='blue').classes('flex-shrink-0')
                            
                            ui.button('Cancel', on_click=sort_dialog.close).classes('w-full mt-4')
                        
                        sort_dialog.open()
                    
                    ui.button('Sort', on_click=open_sort_modal, icon='sort').classes('bg-blue-500 text-white')
                    
                    ui.button('Select All', on_click=select_all, icon='check_box')
                    ui.button('Deselect All', on_click=deselect_all, icon='check_box_outline_blank')
                    ui.button('Open Selected', on_click=open_selected, icon='open_in_new').classes('bg-green-500 text-white')
                    ui.button('', on_click=self._refresh_offers_list, icon='refresh')
            
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
        
        if self.required_keywords_filter:
            filtered_offers = []
            for offer in offers:
                title_lower = offer.get('title', '').lower()
                desc_lower = offer.get('description', '').lower()
                company_lower = offer.get('company', '').lower()
                techs_lower = offer.get('technologies', '').lower()
                
                text_to_search = f"{title_lower} {desc_lower} {company_lower} {techs_lower}"
                
                has_required = any(
                    req_kw in text_to_search
                    for req_kw in self.required_keywords_filter
                )
                
                if has_required:
                    filtered_offers.append(offer)
            offers = filtered_offers
        
        if self.excluded_keywords_filter:
            filtered_offers = []
            for offer in offers:
                title_lower = offer.get('title', '').lower()
                desc_lower = offer.get('description', '').lower()
                company_lower = offer.get('company', '').lower()
                
                should_exclude = False
                for excluded in self.excluded_keywords_filter:
                    if excluded in title_lower or excluded in desc_lower or excluded in company_lower:
                        should_exclude = True
                        break
                
                if not should_exclude:
                    filtered_offers.append(offer)
            offers = filtered_offers
        
        def get_sort_key(offer):
            if self.sort_by == 'scraped_at':
                scraped = offer.get('scraped_at')
                if scraped:
                    if isinstance(scraped, str):
                        try:
                            return datetime.strptime(scraped[:19], '%Y-%m-%d %H:%M:%S')
                        except:
                            return datetime.min
                    return scraped if isinstance(scraped, datetime) else datetime.min
                return datetime.min
            elif self.sort_by == 'valid_until':
                valid = offer.get('valid_until')
                if valid:
                    if isinstance(valid, str):
                        try:
                            return datetime.strptime(valid, '%Y-%m-%d').date()
                        except:
                            return date.min
                    elif isinstance(valid, datetime):
                        return valid.date()
                    return valid if isinstance(valid, date) else date.min
                return date.min
            elif self.sort_by == 'title':
                return offer.get('title', '').lower()
            elif self.sort_by == 'company':
                return offer.get('company', '').lower()
            return ''
        
        offers.sort(key=get_sort_key, reverse=(self.sort_order == 'desc'))
        
        self.offers_data = offers
        
        if self.offers_count_label:
            selected_count = sum(1 for offer in offers if offer.get('id') in self.selected_offers)
            total_count = len(offers)
            self.offers_count_label.text = f'(selected {selected_count}/{total_count})'
        
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
                        
                        if self.offers_count_label:
                            selected_count = sum(1 for offer in self.offers_data if offer.get('id') in self.selected_offers)
                            total_count = len(self.offers_data)
                            self.offers_count_label.text = f'(selected {selected_count}/{total_count})'
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
                        
                        if self.offers_count_label:
                            selected_count = sum(1 for offer in self.offers_data if offer.get('id') in self.selected_offers)
                            total_count = len(self.offers_data)
                            self.offers_count_label.text = f'(selected {selected_count}/{total_count})'
                    
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
