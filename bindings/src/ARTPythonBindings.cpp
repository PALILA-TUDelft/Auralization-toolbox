// Python bindings for the Atmospheric Ray Tracing framework (ITAGeometricalAcoustics)
// Mirrors the MATLAB MEX interface (ARTMatlabExecutable.cpp) using nanobind.

#define _USE_MATH_DEFINES

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <ITAGeo/Atmosphere/HumidityProfiles.h>
#include <ITAGeo/Atmosphere/StratifiedAtmosphere.h>
#include <ITAGeo/Atmosphere/TemperatureProfiles.h>
#include <ITAGeo/Atmosphere/WindProfiles.h>
#include <ITAGeo/Utils/JSON/Atmosphere.h>
#include <ITAPropagationPathSim/AtmosphericRayTracing/EigenraySearch/EigenrayEngine.h>
#include <ITAPropagationPathSim/AtmosphericRayTracing/EigenraySearch/EigenraySettings.h>
#include <ITAPropagationPathSim/AtmosphericRayTracing/Rays.h>
#include <ITAPropagationPathSim/AtmosphericRayTracing/Simulation/ARTEngine.h>
#include <ITAPropagationPathSim/AtmosphericRayTracing/Simulation/ARTSettings.h>

#include <VistaBase/VistaVector3D.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

using namespace ITAGeo;
using namespace ITAPropagationPathSim::AtmosphericRayTracing;


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static VistaVector3D ToVista( const std::vector<double>& v )
{
	if( v.size( ) != 3 )
		throw std::runtime_error( "Expected a 3-element list/tuple for position" );
	return VistaVector3D( static_cast<float>( v[0] ), static_cast<float>( v[1] ), static_cast<float>( v[2] ) );
}

static std::vector<VistaVector3D> ToVistaVec( const std::vector<std::vector<double>>& vecs )
{
	std::vector<VistaVector3D> out;
	out.reserve( vecs.size( ) );
	for( const auto& v : vecs )
		out.push_back( ToVista( v ) );
	return out;
}

static CStratifiedAtmosphere DecodeAtmosphere( const std::string& json )
{
	CStratifiedAtmosphere atmos;
	ITAGeo::Utils::JSON::Decode( atmos, json );
	return atmos;
}

// Parse ray-tracing settings from a Python dict.
// Keys match the MATLAB AtmosphericRayTracer property names.
static Simulation::Settings ParseSimSettings( const nb::dict& d )
{
	Simulation::Settings s;
	if( d.contains( "solverMethod" ) )
	{
		std::string m = nb::cast<std::string>( d["solverMethod"] );
		s.solverMethod = ( m == "euler" ) ? Simulation::EULER : Simulation::RUNGE_KUTTA;
	}
	if( d.contains( "integrationTimeStep" ) )
		s.dIntegrationTimeStep = nb::cast<double>( d["integrationTimeStep"] );
	if( d.contains( "multiThreadingActive" ) )
		s.bMultiThreading = nb::cast<bool>( d["multiThreadingActive"] );
	if( d.contains( "adaptiveIntegrationActive" ) )
		s.adaptiveIntegration.bActive = nb::cast<bool>( d["adaptiveIntegrationActive"] );
	if( d.contains( "adaptiveIntegrationMaxError" ) )
		s.adaptiveIntegration.dMaxError = nb::cast<double>( d["adaptiveIntegrationMaxError"] );
	if( d.contains( "adaptiveIntegrationUncritivalError" ) )
		s.adaptiveIntegration.dUncriticalError = nb::cast<double>( d["adaptiveIntegrationUncritivalError"] );
	if( d.contains( "adaptiveIntegrationMaxLevel" ) )
		s.adaptiveIntegration.iMaxAdaptationLevel = nb::cast<int>( d["adaptiveIntegrationMaxLevel"] );
	return s;
}

static EigenraySearch::Settings ParseEigenraySettings( const nb::dict& d )
{
	EigenraySearch::Settings s;
	if( d.contains( "maxPropagationTime" ) )
		s.rayTracing.maxTime = nb::cast<double>( d["maxPropagationTime"] );
	if( d.contains( "maxReflectionOrder" ) )
		s.rayTracing.maxReflectionOrder = nb::cast<int>( d["maxReflectionOrder"] );
	if( d.contains( "abortOnReceiverDistIncrease" ) )
		s.rayTracing.bAbortOnReceiverDistIncrease = nb::cast<bool>( d["abortOnReceiverDistIncrease"] );
	if( d.contains( "maxReceiverRadius" ) )
		s.rayAdaptation.accuracy.maxReceiverRadius = nb::cast<double>( d["maxReceiverRadius"] );
	if( d.contains( "maxSourceReceiverAngle" ) )
		s.rayAdaptation.accuracy.maxSourceReceiverAngle = nb::cast<double>( d["maxSourceReceiverAngle"] );
	if( d.contains( "maxAngleForGeomSpreading" ) )
		s.rayAdaptation.accuracy.maxAngleForGeomSpreading = nb::cast<double>( d["maxAngleForGeomSpreading"] );
	if( d.contains( "advancedRayZoomingActive" ) )
		s.rayAdaptation.advancedRayZooming.bActive = nb::cast<bool>( d["advancedRayZoomingActive"] );
	if( d.contains( "advancedRayZoomingThreshold" ) )
		s.rayAdaptation.advancedRayZooming.threshold = nb::cast<double>( d["advancedRayZoomingThreshold"] );
	if( d.contains( "abortMaxNAdaptations" ) )
		s.rayAdaptation.abort.maxNAdaptations = nb::cast<int>( d["abortMaxNAdaptations"] );
	if( d.contains( "abortMinAngleResolution" ) )
		s.rayAdaptation.abort.minAngleResolutionDeg = nb::cast<double>( d["abortMinAngleResolution"] );
	return s;
}

// Convert a CRay into a Python dict with all fields the Eigenray dataclass needs.
static nb::dict RayToDict( const std::shared_ptr<CRay>& ray )
{
	nb::dict d;

	const int n = ray->NumPoints( );

	// Timestamps
	nb::list t_list;
	for( int i = 0; i < n; ++i )
		t_list.append( ( *ray )[i].timeStamp );
	d["t"] = t_list;

	// Positions (Mx3)
	nb::list r_list;
	for( int i = 0; i < n; ++i )
	{
		const auto& p = ( *ray )[i].position;
		nb::list row;
		row.append( static_cast<double>( p[0] ) );
		row.append( static_cast<double>( p[1] ) );
		row.append( static_cast<double>( p[2] ) );
		r_list.append( row );
	}
	d["r"] = r_list;

	// Initial direction -> angles
	const auto& dir = ray->InitialDirection( );
	double nx       = static_cast<double>( dir[0] );
	double ny       = static_cast<double>( dir[1] );
	double nz       = static_cast<double>( dir[2] );

	double theta_rad = std::acos( std::clamp( nz, -1.0, 1.0 ) );
	double phi_rad   = std::atan2( ny, nx );
	double theta_deg = theta_rad * 180.0 / M_PI;
	double phi_deg   = phi_rad * 180.0 / M_PI;

	d["theta_deg"]          = theta_deg;
	d["phi_deg"]            = phi_deg;
	d["alpha_deg"]          = 90.0 - theta_deg;
	d["spreading_loss"]     = ray->SpreadingLoss( );
	d["num_reflections"]    = ray->ReflectionOrder( );
	d["receiver_sphere_hit"] = ray->ReceiverHit( );
	d["is_eigenray"]        = ray->IsEigenray( );

	nb::list refl;
	for( int idx : ray->ReflectionIndices( ) )
		refl.append( idx );
	d["reflection_indices"] = refl;

	return d;
}


// ---------------------------------------------------------------------------
// Module definition
// ---------------------------------------------------------------------------

NB_MODULE( _art_core, m )
{
	m.doc( ) = "Python bindings for the Atmospheric Ray Tracing engine (ITAGeometricalAcoustics)";

	// -- version --
	m.def( "version", []( ) { return std::string( "v2025a" ); } );

	// -- create_atmosphere_json --
	m.def(
	    "create_atmosphere_json",
	    []( const std::string& tempProfile, double temperatureCelsius, double humidityPercent, double staticPressurePa ) -> std::string
	    {
		    std::shared_ptr<TemperatureProfiles::ITemperatureProfile> pTemp;
		    if( tempProfile == "isa" )
			    pTemp = std::make_shared<TemperatureProfiles::CISA>( );
		    else
			    pTemp = std::make_shared<TemperatureProfiles::CConstant>( temperatureCelsius + 273.15, staticPressurePa );

		    auto pWind = std::make_shared<WindProfiles::CZero>( );
		    auto pHum  = std::make_shared<HumidityProfiles::CConstant>( humidityPercent );

		    CStratifiedAtmosphere atmos( pTemp, pWind, pHum );
		    return ITAGeo::Utils::JSON::Encode( atmos ).str( );
	    },
	    "temp_profile"_a        = "constant",
	    "temperature_celsius"_a = 15.0,
	    "humidity_percent"_a    = 50.0,
	    "static_pressure_pa"_a  = 101325.0,
	    "Create a JSON string representing a stratified atmosphere.\n"
	    "temp_profile: 'constant' or 'isa'.\n"
	    "Returns the JSON string expected by find_eigenrays / trace_rays." );


	// -- find_eigenrays --
	m.def(
	    "find_eigenrays",
	    []( const std::string& atmosphereJson, const std::vector<double>& source, const std::vector<double>& receiver, const nb::dict& eigenraySettings,
	        const nb::dict& simSettings ) -> nb::tuple
	    {
		    auto atmosphere       = DecodeAtmosphere( atmosphereJson );
		    VistaVector3D srcPos  = ToVista( source );
		    VistaVector3D rcvPos  = ToVista( receiver );

		    EigenraySearch::CEngine engine;
		    if( eigenraySettings.size( ) > 0 )
			    engine.eigenraySettings = ParseEigenraySettings( eigenraySettings );
		    if( simSettings.size( ) > 0 )
			    engine.simulationSettings = ParseSimSettings( simSettings );

		    std::vector<int> totalNumRaysTraced;
		    auto eigenrays = engine.Run( atmosphere, srcPos, rcvPos, totalNumRaysTraced );

		    nb::list rayList;
		    for( const auto& ray : eigenrays )
			    rayList.append( RayToDict( ray ) );

		    return nb::make_tuple( rayList, totalNumRaysTraced );
	    },
	    "atmosphere_json"_a,
	    "source"_a,
	    "receiver"_a,
	    "eigenray_settings"_a = nb::dict( ),
	    "sim_settings"_a      = nb::dict( ),
	    "Find eigenrays between source and receiver.\n"
	    "Returns (list_of_ray_dicts, total_num_rays_traced)." );


	// -- trace_rays --
	m.def(
	    "trace_rays",
	    []( const std::string& atmosphereJson, const std::vector<double>& source, const std::vector<std::vector<double>>& rayDirections,
	        const nb::dict& simSettings ) -> nb::list
	    {
		    auto atmosphere      = DecodeAtmosphere( atmosphereJson );
		    VistaVector3D srcPos = ToVista( source );
		    auto dirs            = ToVistaVec( rayDirections );

		    Simulation::CEngine engine;
		    if( simSettings.size( ) > 0 )
		    {
			    engine.settings = ParseSimSettings( simSettings );
			    if( simSettings.contains( "maxPropagationTime" ) )
				    engine.pExternalWatcher = std::make_shared<Simulation::CAbortAtMaxTime>( nb::cast<double>( simSettings["maxPropagationTime"] ) );
		    }

		    auto rays = engine.Run( atmosphere, srcPos, dirs );

		    nb::list rayList;
		    for( const auto& ray : rays )
			    rayList.append( RayToDict( ray ) );
		    return rayList;
	    },
	    "atmosphere_json"_a,
	    "source"_a,
	    "ray_directions"_a,
	    "sim_settings"_a = nb::dict( ),
	    "Trace rays from source in given directions.\n"
	    "Returns list of ray dicts." );


	// -- benchmark_eigenray_search --
	m.def(
	    "benchmark_eigenray_search",
	    []( const std::string& atmosphereJson, const std::vector<double>& source, const std::vector<double>& receiver, int numRuns,
	        const nb::dict& eigenraySettings, const nb::dict& simSettings ) -> std::vector<double>
	    {
		    auto atmosphere      = DecodeAtmosphere( atmosphereJson );
		    VistaVector3D srcPos = ToVista( source );
		    VistaVector3D rcvPos = ToVista( receiver );

		    EigenraySearch::CEngine engine;
		    engine.eigenraySettings   = ParseEigenraySettings( eigenraySettings );
		    engine.simulationSettings = ParseSimSettings( simSettings );

		    std::vector<double> timings( numRuns );
		    for( int i = 0; i < numRuns; ++i )
		    {
			    auto t0 = std::chrono::high_resolution_clock::now( );
			    engine.Run( atmosphere, srcPos, rcvPos );
			    auto t1    = std::chrono::high_resolution_clock::now( );
			    timings[i] = std::chrono::duration<double>( t1 - t0 ).count( );
		    }
		    return timings;
	    },
	    "atmosphere_json"_a,
	    "source"_a,
	    "receiver"_a,
	    "num_runs"_a,
	    "eigenray_settings"_a,
	    "sim_settings"_a,
	    "Benchmark eigenray search, returns list of measured run-times in seconds." );
}
