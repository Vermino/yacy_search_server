// RankingStructured_p.java
// -----------------------
// part of YaCy
// (C) by Michael Peter Christen; mc@yacy.net
// Licensed under the GNU General Public License v2 or later

package net.yacy.htroot;

import net.yacy.cora.protocol.RequestHeader;
import net.yacy.data.TransactionManager;
import net.yacy.search.Switchboard;
import net.yacy.search.SwitchboardConstants;
import net.yacy.search.query.SearchEventCache;
import net.yacy.server.serverObjects;
import net.yacy.server.serverSwitch;

public class RankingStructured_p {

    public static serverObjects respond(final RequestHeader header, final serverObjects post, final serverSwitch env) {
        final serverObjects prop = new serverObjects();
        final Switchboard sb = (Switchboard) env;

        if (post != null) {
            TransactionManager.checkPostTransaction(header, post);

            sb.setConfig(SwitchboardConstants.SEARCH_RICH_BADGE_ALLOW_HEURISTICS,
                    post.getBoolean(SwitchboardConstants.SEARCH_RICH_BADGE_ALLOW_HEURISTICS));
            sb.setConfig(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_SCHEMA,
                    post.getBoolean(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_SCHEMA));
            sb.setConfig(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_THUMBNAIL,
                    post.getBoolean(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_THUMBNAIL));
            sb.setConfig(SwitchboardConstants.SEARCH_RICH_CAROUSEL_ALLOW_RELAXED,
                    post.getBoolean(SwitchboardConstants.SEARCH_RICH_CAROUSEL_ALLOW_RELAXED));
            sb.setConfig(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_SNIPPET,
                    post.getInt(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_SNIPPET,
                            SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_SNIPPET_DEFAULT));
            sb.setConfig(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_RESULTS,
                    post.getInt(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_RESULTS,
                            SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_RESULTS_DEFAULT));

            SearchEventCache.cleanupEvents(true);
        }

        final boolean badgeHeuristics = sb.getConfigBool(SwitchboardConstants.SEARCH_RICH_BADGE_ALLOW_HEURISTICS,
                SwitchboardConstants.SEARCH_RICH_BADGE_ALLOW_HEURISTICS_DEFAULT);
        final boolean requireSchema = sb.getConfigBool(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_SCHEMA,
                SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_SCHEMA_DEFAULT);
        final boolean requireThumbnail = sb.getConfigBool(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_THUMBNAIL,
                SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_THUMBNAIL_DEFAULT);
        final boolean allowRelaxed = sb.getConfigBool(SwitchboardConstants.SEARCH_RICH_CAROUSEL_ALLOW_RELAXED,
                SwitchboardConstants.SEARCH_RICH_CAROUSEL_ALLOW_RELAXED_DEFAULT);
        final int minSnippet = sb.getConfigInt(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_SNIPPET,
                SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_SNIPPET_DEFAULT);
        final int minResults = sb.getConfigInt(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_RESULTS,
                SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_RESULTS_DEFAULT);

        prop.put(SwitchboardConstants.SEARCH_RICH_BADGE_ALLOW_HEURISTICS, badgeHeuristics ? 1 : 0);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_SCHEMA + ".true", requireSchema ? 1 : 0);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_SCHEMA + ".false", requireSchema ? 0 : 1);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_THUMBNAIL + ".true", requireThumbnail ? 1 : 0);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_REQUIRE_THUMBNAIL + ".false", requireThumbnail ? 0 : 1);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_ALLOW_RELAXED + ".true", allowRelaxed ? 1 : 0);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_ALLOW_RELAXED + ".false", allowRelaxed ? 0 : 1);
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_SNIPPET, Integer.toString(minSnippet));
        prop.put(SwitchboardConstants.SEARCH_RICH_CAROUSEL_MIN_RESULTS, Integer.toString(minResults));

        return prop;
    }
}
