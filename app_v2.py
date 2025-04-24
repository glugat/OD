import json
import re
import requests
import unicodedata
from datetime import datetime
import locale
import numpy as np
import pandas as pd
import plotly.express as pxcre
import plotly.graph_objects as go
from shiny.ui import page_navbar
from shiny import render, reactive
from shiny.express import input, output, render, ui


# ------------------------------------------------------------------ Initialisation des fonctions -----------------------------------------------------------------


def get_weather_data(latitude, longitude, api_key):
    # URL de l'API OpenWeather pour récupérer les données météo actuelles
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric&lang=fr"
    
    # Faire la requête GET
    response = requests.get(url)
    
    # Vérifier que la requête a réussi
    if response.status_code == 200:
        # Retourner la réponse JSON
        data = response.json()
        
        # Afficher la réponse complète pour déboguer
        print(json.dumps(data, indent=4))  # Afficher la réponse de manière lisible
        
        # Vérification de la présence des clés 'name', 'main', 'weather', et 'wind'
        if all(key in data for key in ['name', 'main', 'weather', 'wind']):
            return data
        else:
            print("Clés manquantes dans la réponse de l'API.")
            return None
    else:
        print(f"Erreur API: {response.status_code}")
        return None

def get_job_offers(commune_code, mot_cle="data"):
    # Authentification auprès de France Travail (ex Pôle Emploi)
    token_url = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"
    payload = {
        "grant_type": "client_credentials",
        "client_id": id_api_emploi,
        "client_secret": cle_api_emploi,
        "scope": "api_offresdemploiv2 o2dsoffre"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_response = requests.post(token_url, data=payload, headers=headers)

    if token_response.status_code == 200:
        access_token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        offres_url = "https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search"
        all_results = []

        # Boucle sur 3 tranches de 50 : 0-49, 50-99, 100-149
        for start in range(0, 150, 50):
            headers["Range"] = f"offre {start}-{start + 49}"  # OBLIGATOIRE
            params = {
                "motsCles": mot_cle,
                "commune": commune_code,
                "rayon": 10
            }

            response = requests.get(offres_url, headers=headers, params=params)

            if response.status_code == 200:
                batch = response.json().get("resultats", [])
                all_results.extend(batch)

                # S'arrêter si on a moins de 50 résultats
                if len(batch) < 50:
                    break
            else:
                print(f"❌ Erreur API emploi : {response.status_code}")
                break

        return all_results

    else:
        print(f"❌ Authentification échouée : {token_response.status_code}")
        return None



def get_forecast_data(latitude, longitude, api_key):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={latitude}&lon={longitude}&appid={api_key}&units=metric&lang=fr"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Erreur API (prévisions) : {response.status_code}")
        return None


def normalize_city_name(nom):
    """Nettoie un nom de ville pour les comparaisons internes"""
    nom = unicodedata.normalize('NFKD', str(nom)).encode('ASCII', 'ignore').decode('ASCII')
    nom = re.sub(r"[-']", " ", nom)
    nom = re.sub(r"\s+", " ", nom)
    return nom.strip().lower()


def harmonize_dvf_commune(nom):
    n = nom.strip().upper()
    # Fonction de suffixe ordinal
    def ordinal(i):
        return "1er" if i == 1 else f"{i}e"

    # on capte : PARIS / MARSEILLE / LYON + numéro (avec ou sans zéro) + tout suffixe non numérique
    m = re.match(r"^(PARIS|MARSEILLE|LYON)\s*0?(\d{1,2})\D*$", n)
    if m:
        ville = m.group(1).capitalize()      # Paris, Marseille ou Lyon
        i = int(m.group(2))
        return f"{ville} {ordinal(i)}"

    # Sinon : simple Title Case
    return nom.title()


# ------------------------------------------------------------- Importation et traitement des données -------------------------------------------------------------


# Importation des données
communes_original = pd.read_excel("communes-france-2025_v5.xlsx")
appart = pd.read_csv("m2 pour appart.csv", encoding='ISO-8859-1', sep=";")
maisons = pd.read_csv("m2 pour les maisons.csv", encoding='ISO-8859-1', sep=";")
appart_petit = pd.read_csv("m2 pour appart 1 a 2 pieces.csv", encoding='ISO-8859-1', sep=";")
appart_grand = pd.read_csv("m2 pour appart 3 piece et plus.csv", encoding='ISO-8859-1', sep=";")

salaireNet = pd.read_csv("salaireNET.csv")

# Traitement des données
communes = communes_original

# Ajout d'une colonne ville_regroupee dans chaque fichier
for df in [appart, maisons, appart_petit, appart_grand]:
    df["ville_regroupee"] = df["LIBGEO"].str.strip()
    df["ville_norm"] = df["ville_regroupee"].apply(normalize_city_name)
    df["ville_display"] = df["ville_regroupee"].str.title()



# Récupérer la liste des régions
regions = communes['reg_nom'].unique()

# Récupérer la liste des départements
departements = communes['dep_nom'].unique()

# Récupérer la liste des villes
villes = communes['nom_standard'].unique()


# API
cle_api_meteo = "dbdb2efe52cbc2eb72fc3ac12129ab25"
id_api_emploi = "PAR_comparateurdevilles_524d3415d8764b92f1847759dd3dfb4b2f238c9f3a1a51002ed6a66e9abe2ba7"
cle_api_emploi = "292f9efde41bcfa019158b99415203324ef02008a8243af6a570a164d41e72ac"
cle_api_maps = "AIzaSyASVaZQeDz3A_YKSea75jqCqcEKGjeu3rk"


# -------------------------------------------------------------------------- Application --------------------------------------------------------------------------

# Titre
ui.page_opts(title = ui.strong("Comparateur de villes"), fillable=True)

# Mode sombre
#ui.input_dark_mode(mode = "light") 

# Barre de navigation
with ui.navset_card_pill(id="tab"):

    # Première page
    #with ui.nav_panel("Présentation du projet"):
        #ui.h4(ui.strong("Présentation du projet"))

    # Deuxième page
    with ui.nav_panel("Sélection des  villes"):
        ui.h4(ui.strong("📌 Sélection des villes à comparer"))

        with ui.layout_columns():  
            with ui.card():  
                ui.card_header("Première ville")

                # Choix - Région 1
                region_select = ui.input_selectize(  
                    "selectize_r1",  
                    "Choisir la région :",  # Mise à jour du texte pour "Choisir la région"
                    {region: region for region in regions},  # Créer un dictionnaire avec les noms des régions
                )
                region_select
                
                # Choix - Département 1
                departement_select = ui.input_selectize(  
                    "selectize_d1",  
                    "Choisir le département :",  # Mise à jour du texte pour "Choisir le département"
                    {},  # Les départements seront mis à jour dynamiquement en fonction de la région
                )
                
                # Choix - Ville 1
                ville_select = ui.input_selectize(  
                    "selectize_v1",  
                    "Choisir la ville :",  # Mise à jour du texte pour "Choisir la ville"
                    {},  # Les villes seront mises à jour dynamiquement en fonction du département
                )

                # Fonction générique pour mettre à jour les départements en fonction de la région choisie
                @render.ui
                def update_departments():
                    selected_region = input.selectize_r1()
                    if selected_region:
                        # Filtrer les départements par région
                        departments_in_region = communes[communes['reg_nom'] == selected_region]['dep_nom'].unique()
                        return ui.input_selectize(
                            "selectize_d1",  
                            "Choisir le département :",  
                            {dept: dept for dept in departments_in_region}  # Filtrer les départements par région
                        )
                    return ui.input_selectize("selectize_d1", "Choisir le département :", {})

                # Fonction pour mettre à jour les villes en fonction du département choisi
                @render.ui
                def update_cities():
                    selected_departement = input.selectize_d1()
                    if selected_departement:
                        # Filtrer les villes par département
                        cities_in_departement = communes[communes['dep_nom'] == selected_departement]['nom_standard'].unique()
                        return ui.input_selectize(
                            "selectize_v1",  
                            "Choisir la ville :",  
                            {city: city for city in cities_in_departement}  # Filtrer les villes par département
                        )
                    return ui.input_selectize("selectize_v1", "Choisir la ville :", {})


            with ui.card():  
                ui.card_header("Seconde ville")

                # Choix - Région 2
                region_select2 = ui.input_selectize(  
                    "selectize_r2",  
                    "Choisir la région :",  # Mise à jour du texte pour "Choisir la région"
                    {region: region for region in regions},  # Créer un dictionnaire avec les noms des régions
                )
                region_select2
                
                # Choix - Département 2
                departement_select2 = ui.input_selectize(  
                    "selectize_d2",  
                    "Choisir le département :",  # Mise à jour du texte pour "Choisir le département"
                    {},  # Les départements seront mis à jour dynamiquement en fonction de la région
                )
                
                # Choix - Ville 2
                ville_select2 = ui.input_selectize(  
                    "selectize_v2",  
                    "Choisir la ville :",  # Mise à jour du texte pour "Choisir la ville"
                    {},  # Les villes seront mises à jour dynamiquement en fonction du département
                )

                # Fonction générique pour mettre à jour les départements en fonction de la région choisie
                @render.ui
                def update_departments_2():
                    selected_region = input.selectize_r2()
                    if selected_region:
                        # Filtrer les départements par région
                        departments_in_region = communes[communes['reg_nom'] == selected_region]['dep_nom'].unique()
                        return ui.input_selectize(
                            "selectize_d2",  
                            "Choisir le département :",  
                            {dept: dept for dept in departments_in_region}  # Filtrer les départements par région
                        )
                    return ui.input_selectize("selectize_d2", "Choisir le département :", {})

                # Fonction pour mettre à jour les villes en fonction du département choisi
                @render.ui
                def update_cities_2():
                    selected_departement = input.selectize_d2()
                    if selected_departement:
                        # Filtrer les villes par département
                        cities_in_departement = communes[communes['dep_nom'] == selected_departement]['nom_standard'].unique()
                        return ui.input_selectize(
                            "selectize_v2",  
                            "Choisir la ville :",  
                            {city: city for city in cities_in_departement}  # Filtrer les villes par département
                        )
                    return ui.input_selectize("selectize_v2", "Choisir la ville :", {})
                
                # Fonction pour stocker les villes sélectionnées dans des variables réactives
                @render.ui
                def store_cities():
                    ville_1 = input.selectize_v1()
                    ville_2 = input.selectize_v2()

    # Troisième page
    with ui.nav_menu("Comparaison des villes"):

        with ui.nav_panel("Profil territorial"):
            ui.h4(ui.strong("📌 Profil territorial"))

            with ui.layout_columns(fill=True):
                with ui.card(full_screen=True):
                    # Profil territorial - Ville 1
                    @render.ui
                    def display_caracteristics_1():
                        ville_1 = input.selectize_v1()
                        if ville_1:
                            ville_data = communes[communes["nom_standard"] == ville_1]
                            if not ville_data.empty:
                                v = ville_data.iloc[0]
                                return ui.div(
                                    ui.h5(f"🏙️ Caractéristiques de {ville_1}"),
                                    ui.hr(),
                                    ui.p("👥 ", ui.strong("Population : "), f"{int(v['population']):,} habitants"),
                                    ui.p("📐 ", ui.strong("Superficie : "), f"{v['superficie_km2']} km²"),
                                    ui.p("📊 ", ui.strong("Densité : "), f"{v['densite']} hab/km²"),
                                    ui.p("🏞️ ", ui.strong("Altitude moyenne : "), f"{v['altitude_moyenne']} m"),
                                    ui.p("⬇️ ", ui.strong("Altitude min. : "), f"{v['altitude_minimale']} m"),
                                    ui.p("⬆️ ", ui.strong("Altitude max. : "), f"{v['altitude_maximale']} m"),
                                    ui.p("📍 ", ui.strong("Statut dans l'unité urbaine : "), v['statut_commune_unite_urbaine']),
                                    ui.p("🏘️ ", ui.strong("Taille unité urbaine : "), v['taille_unite_urbaine']),
                                    ui.p("✅ ", ui.strong("Niveau d'équipement et de services: "), v['niveau_equipements_services'])
                                )
                        return ui.div(
                            ui.h5("Première ville non sélectionnée"),
                            ui.p("Veuillez choisir la première ville dans l'onglet 'Sélection des villes'.")
                        )

                with ui.card(full_screen=True):
                    # Profil territorial - Ville 2
                    @render.ui
                    def display_caracteristics_2():
                        ville_2 = input.selectize_v2()
                        if ville_2:
                            ville_data = communes[communes["nom_standard"] == ville_2]
                            if not ville_data.empty:
                                v = ville_data.iloc[0]
                                return ui.div(
                                    ui.h5(f"🏙️ Caractéristiques de {ville_2}"),
                                    ui.hr(),
                                    ui.p("👥 ", ui.strong("Population : "), f"{int(v['population']):,} habitants"),
                                    ui.p("📐 ", ui.strong("Superficie : "), f"{v['superficie_km2']} km²"),
                                    ui.p("📊 ", ui.strong("Densité : "), f"{v['densite']} hab/km²"),
                                    ui.p("🏞️ ", ui.strong("Altitude moyenne : "), f"{v['altitude_moyenne']} m"),
                                    ui.p("⬇️ ", ui.strong("Altitude min. : "), f"{v['altitude_minimale']} m"),
                                    ui.p("⬆️ ", ui.strong("Altitude max. : "), f"{v['altitude_maximale']} m"),
                                    ui.p("📍 ", ui.strong("Statut dans l'unité urbaine : "), v['statut_commune_unite_urbaine']),
                                    ui.p("🏘️ ", ui.strong("Taille unité urbaine : "), v['taille_unite_urbaine']),
                                    ui.p("✅ ", ui.strong("Niveau d'équipement et de services: "), v['niveau_equipements_services'])
                                )
                        elif input.selectize_v1():
                            return ui.div(
                                ui.h5("Seconde ville non sélectionnée"),
                                ui.p("Veuillez choisir la seconde ville pour activer la comparaison.")
                            )
                        return ui.div(
                            ui.h5("Aucune ville sélectionnée"),
                            ui.p("Veuillez choisir les villes dans l'onglet 'Sélection des villes'.")
                        )

        with ui.nav_panel("Météo"):
            ui.h4(ui.strong("📌 Météo"))

            with ui.layout_columns(): 
                with ui.card():  
                    # Prévisions météo - Ville 1
                    @render.ui
                    def display_weather_1():
                        ville_1 = input.selectize_v1()

                        if ville_1:
                            coord_ville_1 = communes[communes['nom_standard'] == ville_1].iloc[0]

                            lat = coord_ville_1['latitude_centre']
                            lon = coord_ville_1['longitude_centre']

                            weather_1 = get_weather_data(lat, lon, cle_api_meteo)
                            forecast_data = get_forecast_data(lat, lon, cle_api_meteo)

                            if weather_1 and forecast_data:
                                content = []

                                # Météo actuelle
                                icon_url_1 = f"http://openweathermap.org/img/wn/{weather_1['weather'][0]['icon']}@2x.png"
                                content.append(
                                    ui.div(
                                        ui.h5(f"🌤️ Météo actuelle à {ville_1}"),
                                        ui.img(src=icon_url_1, height="60px"),
                                        ui.p(f"🌡️ Température : {weather_1['main']['temp']}°C"),
                                        ui.p(f"🌥️ Description : {weather_1['weather'][0]['description'].capitalize()}"),
                                        ui.p(f"💧 Humidité : {weather_1['main']['humidity']}%"),
                                        ui.p(f"💨 Vent : {weather_1['wind']['speed']} m/s"),
                                    )
                                )

                                # Prévisions de la semaine
                                for item in forecast_data['list']:
                                    if "12:00:00" in item['dt_txt']:
                                        date = item['dt_txt'].split(" ")[0]
                                        date_obj = datetime.strptime(date, "%Y-%m-%d")
                                        date_text = date_obj.strftime("%A %d %B %Y")

                                        temp = item['main']['temp']
                                        desc = item['weather'][0]['description']
                                        icon = item['weather'][0]['icon']
                                        icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"

                                        content.append(
                                            ui.div(
                                                ui.hr(),
                                                ui.h5(f"🗓️ {date_text.capitalize()}"),
                                                ui.img(src=icon_url, height="50px"),
                                                ui.p(f"🌡️ Température : {temp}°C"),
                                                ui.p(f"🌥️ Description : {desc.capitalize()}"),
                                            )
                                        )

                                return ui.div(*content)

                        return ui.p("Sélectionne une ville pour afficher les prévisions météo.")


                with ui.card():  
                    # Prévisions météo - Ville 2
                    @render.ui
                    def display_weather_2():
                        ville_2 = input.selectize_v2()

                        if ville_2:
                            coord_ville_2 = communes[communes['nom_standard'] == ville_2].iloc[0]

                            lat = coord_ville_2['latitude_centre']
                            lon = coord_ville_2['longitude_centre']

                            weather_2 = get_weather_data(lat, lon, cle_api_meteo)
                            forecast_data = get_forecast_data(lat, lon, cle_api_meteo)

                            if weather_2 and forecast_data:
                                content = []

                                # Météo actuelle
                                icon_url_1 = f"http://openweathermap.org/img/wn/{weather_2['weather'][0]['icon']}@2x.png"
                                content.append(
                                    ui.div(
                                        ui.h5(f"🌤️ Météo actuelle à {ville_2}"),
                                        ui.img(src=icon_url_1, height="60px"),
                                        ui.p(f"🌡️ Température : {weather_2['main']['temp']}°C"),
                                        ui.p(f"🌥️ Description : {weather_2['weather'][0]['description'].capitalize()}"),
                                        ui.p(f"💧 Humidité : {weather_2['main']['humidity']}%"),
                                        ui.p(f"💨 Vent : {weather_2['wind']['speed']} m/s"),
                                    )
                                )

                                # Prévisions de la semaine
                                for item in forecast_data['list']:
                                    if "12:00:00" in item['dt_txt']:
                                        date = item['dt_txt'].split(" ")[0]
                                        date_obj = datetime.strptime(date, "%Y-%m-%d")
                                        date_text = date_obj.strftime("%A %d %B %Y")

                                        temp = item['main']['temp']
                                        desc = item['weather'][0]['description']
                                        icon = item['weather'][0]['icon']
                                        icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"

                                        content.append(
                                            ui.div(
                                                ui.hr(),
                                                ui.h5(f"📅 {date_text.capitalize()}"),
                                                ui.img(src=icon_url, height="50px"),
                                                ui.p(f"🌡️ Température : {temp}°C"),
                                                ui.p(f"🌥️ Description : {desc.capitalize()}"),
                                            )
                                        )

                                return ui.div(*content)

                        return ui.p("Sélectionne une ville pour afficher les prévisions météo.")

        with ui.nav_panel("Emploi"):
            ui.h4(ui.strong("📌 Emploi"))

            with ui.layout_columns():
                with ui.card():
                    ui.HTML("""
                        <!DOCTYPE html>
                        <html lang="fr">
                        <head>
                            <script src="https://francetravail.io/data/widget/pe-offres-emploi.js"></script>
                        </head>
                        <body>
                            <pe-offres-emploi></pe-offres-emploi>
                            <script>
                                var macarte = document.querySelector('pe-offres-emploi');
                                macarte.options = {
                                    rechercheAuto: false,
                                    zoomInitial: 5,
                                    positionInitiale: [2.09,46.505],
                                    technicalParameters: {
                                        range: { value: '0-49', show: false, order: 1},
                                        sort: { value: 1, show: true, order: 3}
                                    },
                                    criterias: {
                                        domaine: { value: null, show: false, order: 1},
                                        codeROME: { value: null, show: false, order: 1},
                                        appellation: { value: null, show: false, order: 1},
                                        theme: { value: null, show: false, order: 1},
                                        secteurActivite: { value: null, show: false, order: 1},
                                        experience: { value: null, show: false, order: 1},
                                        typeContrat: { value: null, show: true, order: 2},
                                        natureContrat: { value: null, show: false, order: 1},
                                        qualification: { value: null, show: false, order: 1},
                                        tempsPlein: { value: null, show: true, order: 4},
                                        commune: { value: null, show: true, order: 1},
                                        distance: { value: null, show: false, order: 1, min: 0, max: 100},
                                        departement: { value: null, show: false, order: 1},
                                        inclureLimitrophes: { value: null, show: false, order: 1},
                                        region: { value: null, show: false, order: 1},
                                        paysContinent: { value: null, show: false, order: 1},
                                        niveauFormation: { value: null, show: false, order: 1},
                                        permis: { value: null, show: false, order: 1},
                                        motsCles: { value: null, show: true, order: 0},
                                        salaireMin: { value: null, show: false, order: 1, min: 0, max: 100},
                                        periodeSalaire: { value: null, show: false, order: 1},
                                        accesTravailleurHandicape: { value: null, show: false, order: 1},
                                        publieeDepuis: { value: null, show: false, order: 1},
                                        offresMRS: { value: null, show: false, order: 1},
                                        grandDomaine: { value: null, show: false, order: 1},
                                        experienceExigence: { value: null, show: false, order: 1}
                                    }
                                };
                            </script>
                        </body>
                        </html>
                        """)
    
                with ui.card():
                    ui.HTML("""
                        <!DOCTYPE html>
                        <html lang="fr">
                        <head>
                            <script src="https://francetravail.io/data/widget/pe-offres-emploi.js"></script>
                        </head>
                        <body>
                            <pe-offres-emploi></pe-offres-emploi>
                            <script>
                                var macarte = document.querySelector('pe-offres-emploi');
                                macarte.options = {
                                    rechercheAuto: false,
                                    zoomInitial: 5,
                                    positionInitiale: [2.09,46.505],
                                    technicalParameters: {
                                        range: { value: '0-49', show: false, order: 1},
                                        sort: { value: 1, show: true, order: 3}
                                    },
                                    criterias: {
                                        domaine: { value: null, show: false, order: 1},
                                        codeROME: { value: null, show: false, order: 1},
                                        appellation: { value: null, show: false, order: 1},
                                        theme: { value: null, show: false, order: 1},
                                        secteurActivite: { value: null, show: false, order: 1},
                                        experience: { value: null, show: false, order: 1},
                                        typeContrat: { value: null, show: true, order: 2},
                                        natureContrat: { value: null, show: false, order: 1},
                                        qualification: { value: null, show: false, order: 1},
                                        tempsPlein: { value: null, show: true, order: 4},
                                        commune: { value: null, show: true, order: 1},
                                        distance: { value: null, show: false, order: 1, min: 0, max: 100},
                                        departement: { value: null, show: false, order: 1},
                                        inclureLimitrophes: { value: null, show: false, order: 1},
                                        region: { value: null, show: false, order: 1},
                                        paysContinent: { value: null, show: false, order: 1},
                                        niveauFormation: { value: null, show: false, order: 1},
                                        permis: { value: null, show: false, order: 1},
                                        motsCles: { value: null, show: true, order: 0},
                                        salaireMin: { value: null, show: false, order: 1, min: 0, max: 100},
                                        periodeSalaire: { value: null, show: false, order: 1},
                                        accesTravailleurHandicape: { value: null, show: false, order: 1},
                                        publieeDepuis: { value: null, show: false, order: 1},
                                        offresMRS: { value: null, show: false, order: 1},
                                        grandDomaine: { value: null, show: false, order: 1},
                                        experienceExigence: { value: null, show: false, order: 1}
                                    }
                                };
                            </script>
                        </body>
                        </html>
                        """)


        with ui.nav_panel("Logement"):
            ui.h4(ui.strong("📌 Logement"))

            # ui.layout_columns permet de placer les cartes côte à côte
            # fill=True les rendra responsive et utilisera l'espace disponible
            with ui.layout_columns(fill=True):

                # Carte pour la première ville sélectionnée
                with ui.card(full_screen=True): # full_screen=True ajoute l'option d'agrandissement

                    # Contenu réactif de la carte 1
                    # Cette fonction @render.ui est exécutée par Shiny chaque fois que
                    # input.selectize_v1() change. Son RETURN génère le HTML/UI affiché ICI.
                    @render.ui # PAS besoin de ui.output_ui() séparé en shiny.express
                    def contenu_card_ville1():
                        # On lit directement la valeur de l'input de sélection de la ville 1
                        ville1 = input.selectize_v1()

                        if ville1:
                            def get_prix(df, ville):
                                ville_norm = normalize_city_name(ville)
                                rows = df[df["ville_norm"] == ville_norm]
                                if not rows.empty:
                                    try:
                                        valeurs = rows["loypredm2"].astype(str).str.replace(",", ".").str.replace("\u202f", "").astype(float)
                                        return round(valeurs.mean(), 2)
                                    except:
                                        return "Non numérique"
                                return "Non disponible"

                            return ui.div(
                                ui.h5(f"🏙️ Logements de {ville1}"),
                                ui.hr(),
                                ui.h5("Prix des loyers (€/m²/mois)"),
                                ui.p("🏠 Maisons : ", f"{get_prix(maisons, ville1)} €"),
                                ui.p("🏢 Appartements : ", f"{get_prix(appart, ville1)} €"),
                                ui.p("1️⃣ Appartements (1-2 pièces) : ", f"{get_prix(appart_petit, ville1)} €"),
                                ui.p("3️⃣ Appartements (3+ pièces) : ", f"{get_prix(appart_grand, ville1)} €"),

                                ui.hr(),
                                ui.h5("💰 Prix d'achat immobilier (€/m²)"),
                            )
                        
                        

                        else:
                            # Message affiché si la première ville n'est pas sélectionnée
                            return ui.div(
                                ui.h5("Première ville non sélectionnée"),
                                ui.p("Veuillez choisir la première ville sur l'onglet 'Sélection des villes'.")
                            )

                    # Le contenu de cette fonction @render.ui s'affichera automatiquement ici.
                    # NE PAS ajouter ui.output_ui("contenu_card_ville1") ici.


                # Carte pour la seconde ville sélectionnée
                with ui.card(full_screen=True): # full_screen=True ajoute l'option d'agrandissement

                    # Contenu réactif de la carte 2
                    # Cette fonction @render.ui est exécutée chaque fois que
                    # input.selectize_v2() change. Son RETURN génère le HTML/UI affiché ICI.
                    @render.ui # PAS besoin de ui.output_ui() séparé en shiny.express
                    def contenu_card_ville2():
                        # On lit directement la valeur de l'input de sélection de la ville 2
                        ville2 = input.selectize_v2()

                        if ville2:
                            def get_prix(df, ville):
                                ville_norm = normalize_city_name(ville)
                                rows = df[df["ville_norm"] == ville_norm]
                                if not rows.empty:
                                    try:
                                        valeurs = rows["loypredm2"].astype(str).str.replace(",", ".").str.replace("\u202f", "").astype(float)
                                        return round(valeurs.mean(), 2)
                                    except:
                                        return "Non numérique"
                                return "Non disponible"

                            

                            return ui.div(
                                ui.h5(f"🏙️ Logements de {ville2}"),
                                ui.hr(),
                                ui.h5("Prix des loyers (€/m²/mois)"),
                                ui.p("🏠 Maisons : ", f"{get_prix(maisons, ville2)} €"),
                                ui.p("🏢 Appartements : ", f"{get_prix(appart, ville2)} €"),
                                ui.p("1️⃣ Appartements (1-2 pièces) : ", f"{get_prix(appart_petit, ville2)} €"),
                                ui.p("3️⃣ Appartements (3+ pièces) : ", f"{get_prix(appart_grand, ville2)} €"),

                                ui.hr(),
                                ui.h5("💰 Prix d'achat immobilier (€/m²)"),
                            )

                        elif input.selectize_v1(): # Si une ville 1 est sélectionnée mais pas de ville 2
                             # Message si seulement la ville 1 est sélectionnée
                             return ui.div(
                                 ui.h5("Seconde ville non sélectionnée"),
                                 ui.p("Veuillez choisir une seconde ville sur l'onglet 'Sélection des villes' pour la comparaison.")
                             )
                        else: # Si aucune ville (ni la 1ère ni la 2ème) n'est sélectionnée
                             # Message si aucune ville n'est sélectionnée du tout
                             return ui.div(
                                 ui.h5("Aucune ville sélectionnée"),
                                 ui.p("Veuillez choisir les villes sur l'onglet 'Sélection des villes'.")
                             )

        with ui.nav_panel("Autres"):
            ui.h4("📌 Autres")

            with ui.layout_columns():
                with ui.card():
                    ui.card_header("Carte de la première ville")

                    @render.ui
                    def map_ville_1():
                        selected_ville = input.selectize_v1()
                        if selected_ville:
                            ville_data = communes[communes['nom_standard'] == selected_ville]
                            if not ville_data.empty:
                                lat = ville_data['latitude_centre'].values[0]
                                lon = ville_data['longitude_centre'].values[0]
                            else:
                                lat, lon = 46.6, 1.88
                        else:
                            lat, lon = 46.6, 1.88

                        return ui.HTML(f"""
                            <input id="pac-input" class="controls" type="text" placeholder="Rechercher un lieu sur la carte"
                                style="margin-top:10px; width: 300px; height: 40px; font-size: 16px; padding: 5px 10px; z-index: 1000; position: absolute; left: 50%; transform: translateX(-50%);">

                            <div id="map1" style="height: 500px; width: 100%; border-radius: 12px; box-shadow: 0px 2px 6px rgba(0,0,0,0.2); margin-top: 1rem;"></div>

                            <script>
                                function initMap1() {{
                                    const map = new google.maps.Map(document.getElementById("map1"), {{
                                        center: {{lat: {lat}, lng: {lon}}},
                                        zoom: 12,
                                        mapTypeId: 'roadmap'
                                    }});

                                    const input = document.getElementById("pac-input");
                                    const searchBox = new google.maps.places.SearchBox(input);
                                    map.controls[google.maps.ControlPosition.TOP_CENTER].push(input);

                                    map.addListener("bounds_changed", function() {{
                                        searchBox.setBounds(map.getBounds());
                                    }});

                                    let markers = [];

                                    searchBox.addListener("places_changed", function() {{
                                        const places = searchBox.getPlaces();
                                        if (places.length == 0) return;

                                        markers.forEach(marker => marker.setMap(null));
                                        markers = [];

                                        const bounds = new google.maps.LatLngBounds();

                                        places.forEach(place => {{
                                            if (!place.geometry || !place.geometry.location) return;

                                            markers.push(new google.maps.Marker({{
                                                map,
                                                title: place.name,
                                                position: place.geometry.location,
                                            }}));

                                            if (place.geometry.viewport) {{
                                                bounds.union(place.geometry.viewport);
                                            }} else {{
                                                bounds.extend(place.geometry.location);
                                            }}
                                        }});

                                        map.fitBounds(bounds);
                                    }});
                                }}
                                window.initMap1 = initMap1;
                            </script>

                            <script async defer
                                src="https://maps.googleapis.com/maps/api/js?key={cle_api_maps}&callback=initMap1&libraries=places">
                            </script>
                        """)


                with ui.card():
                    ui.card_header("Carte de la seconde ville")

                    @render.ui
                    def map_ville_2():
                        selected_ville = input.selectize_v2()
                        if selected_ville:
                            ville_data = communes[communes['nom_standard'] == selected_ville]
                            if not ville_data.empty:
                                lat = ville_data['latitude_centre'].values[0]
                                lon = ville_data['longitude_centre'].values[0]
                            else:
                                lat, lon = 46.6, 1.88
                        else:
                            lat, lon = 46.6, 1.88

                        return ui.HTML(f"""
                            <input id="pac-input-2" class="controls" type="text" placeholder="Rechercher un lieu"
                                style="margin-top:10px; width: 300px; height: 40px; font-size: 16px; padding: 5px 10px; z-index: 1000; position: absolute; left: 50%; transform: translateX(-50%);">

                            <div id="map2" style="height: 500px; width: 100%; border-radius: 12px; box-shadow: 0px 2px 6px rgba(0,0,0,0.2); margin-top: 1rem;"></div>

                            <script>
                                function initMap2() {{
                                    const map = new google.maps.Map(document.getElementById("map2"), {{
                                        center: {{lat: {lat}, lng: {lon}}},
                                        zoom: 12,
                                        mapTypeId: 'roadmap'
                                    }});

                                    const input = document.getElementById("pac-input-2");
                                    const searchBox = new google.maps.places.SearchBox(input);
                                    map.controls[google.maps.ControlPosition.TOP_CENTER].push(input);

                                    map.addListener("bounds_changed", function() {{
                                        searchBox.setBounds(map.getBounds());
                                    }});

                                    let markers = [];

                                    searchBox.addListener("places_changed", function() {{
                                        const places = searchBox.getPlaces();
                                        if (places.length == 0) return;

                                        markers.forEach(marker => marker.setMap(null));
                                        markers = [];

                                        const bounds = new google.maps.LatLngBounds();

                                        places.forEach(place => {{
                                            if (!place.geometry || !place.geometry.location) return;

                                            markers.push(new google.maps.Marker({{
                                                map,
                                                title: place.name,
                                                position: place.geometry.location,
                                            }}));

                                            if (place.geometry.viewport) {{
                                                bounds.union(place.geometry.viewport);
                                            }} else {{
                                                bounds.extend(place.geometry.location);
                                            }}
                                        }});

                                        map.fitBounds(bounds);
                                    }});
                                }}
                                window.initMap2 = initMap2;
                            </script>

                            <script async defer
                                src="https://maps.googleapis.com/maps/api/js?key={cle_api_maps}&callback=initMap2&libraries=places">
                            </script>
                        """)


